import asyncio
import json
import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple
from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_GeogFromText
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache
from app.core.config import settings
from app.models.hospital import Hospital
from app.schemas.hospital import HospitalNearbyItem, HospitalNearbyResponse
from app.services.incident_service import extract_incident_lat_lng
from app.services.realtime import haversine_distance_m
from app.services.routing_service import routing_service

logger = logging.getLogger("smartroute.hospitals")


class HospitalService:
    """Service orchestrating spatial hospital search, specialty matching, and routing."""

    async def ensure_hospitals_seeded(self, db: AsyncSession) -> int:
        """
        Idempotently seed default emergency hospitals if database table is empty.
        Reads from backend/data/default_hospitals.json.
        """
        try:
            count_stmt = select(func.count(Hospital.id))
            existing_count = (await db.execute(count_stmt)).scalar_one()
            if existing_count > 0:
                return existing_count

            data_file = Path(__file__).resolve().parent.parent.parent / "data" / "default_hospitals.json"
            if not data_file.exists():
                logger.warning("Default hospitals file not found at %s", data_file)
                return 0

            with open(data_file, "r", encoding="utf-8") as f:
                items = json.load(f)

            inserted = 0
            for item in items:
                name = item.get("name")
                lat = item.get("lat")
                lng = item.get("lng")
                if not name or lat is None or lng is None:
                    continue

                point_geom = WKTElement(f"POINT({lng} {lat})", srid=4326)
                types = item.get("emergency_types") or ["general"]
                hosp = Hospital(
                    name=name,
                    location=point_geom,
                    phone=item.get("phone"),
                    address=item.get("address"),
                    has_emergency=True,
                    specialties=types,
                    emergency_types=types,
                    simulated_beds=item.get("simulated_beds", 30),
                    beds_simulated=True,
                    is_24x7=item.get("is_24x7", True),
                    source="osm",
                    osm_attribution="© OpenStreetMap contributors",
                    osm_id=item.get("osm_id"),
                )
                db.add(hosp)
                inserted += 1

            await db.commit()
            logger.info("Successfully seeded %d emergency hospitals into database.", inserted)
            return inserted
        except Exception as exc:
            logger.error("Failed to seed hospitals: %s", exc, exc_info=True)
            return 0

    async def rank_hospitals(
        self,
        origin: Tuple[float, float],
        emergency_type: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> HospitalNearbyResponse:
        """
        Rank nearest hospitals with emergency capabilities.
        1. Auto-seeds default emergency hospitals if database table is empty.
        2. Prefilter candidates within HOSPITAL_SEARCH_RADIUS_M using PostGIS ST_DWithin.
        3. If no hospitals within radius, falls back to nearest available emergency facilities.
        4. Real route calculation for top HOSPITAL_ROUTE_COUNT (incorporating traffic & incidents).
        5. Rank by adjusted ETA, returning route geometry for the best option only.
        """
        origin_lat, origin_lng = origin
        cache_key = f"hospitals:{round(origin_lat, 3)},{round(origin_lng, 3)}:{emergency_type or 'all'}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        if db is None:
            return HospitalNearbyResponse(hospitals=[])

        # Auto-seed if database is empty
        count_stmt = select(func.count(Hospital.id))
        total_in_db = (await db.execute(count_stmt)).scalar_one()
        if total_in_db == 0:
            await self.ensure_hospitals_seeded(db)

        origin_geog = ST_GeogFromText(f"SRID=4326;POINT({origin_lng} {origin_lat})")
        distance_expr = ST_Distance(Hospital.location, origin_geog)

        candidates: List[Tuple[Hospital, bool]] = []  # (hospital, matches_type)

        clean_type = emergency_type.strip().lower() if emergency_type else None

        if clean_type:
            # Attempt to query hospitals matching the requested emergency type within radius
            stmt_match = (
                select(Hospital)
                .where(ST_DWithin(Hospital.location, origin_geog, settings.HOSPITAL_SEARCH_RADIUS_M))
                .where(Hospital.emergency_types.contains([clean_type]))
                .order_by(distance_expr.asc())
                .limit(settings.HOSPITAL_PREFILTER_COUNT)
            )
            res_match = await db.execute(stmt_match)
            matched_hospitals = list(res_match.scalars().all())

            if matched_hospitals:
                candidates = [(h, True) for h in matched_hospitals]
            else:
                # Fall back to general emergency hospitals within radius
                logger.info("No hospitals matched emergency type '%s'; checking general emergency within radius.", clean_type)
                stmt_fallback = (
                    select(Hospital)
                    .where(ST_DWithin(Hospital.location, origin_geog, settings.HOSPITAL_SEARCH_RADIUS_M))
                    .where(Hospital.has_emergency.is_(True))
                    .order_by(distance_expr.asc())
                    .limit(settings.HOSPITAL_PREFILTER_COUNT)
                )
                res_fallback = await db.execute(stmt_fallback)
                candidates = [(h, False) for h in res_fallback.scalars().all()]
        else:
            stmt_all = (
                select(Hospital)
                .where(ST_DWithin(Hospital.location, origin_geog, settings.HOSPITAL_SEARCH_RADIUS_M))
                .where(Hospital.has_emergency.is_(True))
                .order_by(distance_expr.asc())
                .limit(settings.HOSPITAL_PREFILTER_COUNT)
            )
            res_all = await db.execute(stmt_all)
            candidates = [(h, True) for h in res_all.scalars().all()]

        # If still empty (e.g. user is beyond 15 km radius), expand to nearest facilities across network
        if not candidates:
            logger.info("No hospitals within %dm; expanding search to closest emergency facilities.", settings.HOSPITAL_SEARCH_RADIUS_M)
            if clean_type:
                stmt_expanded_match = (
                    select(Hospital)
                    .where(Hospital.emergency_types.contains([clean_type]))
                    .order_by(distance_expr.asc())
                    .limit(settings.HOSPITAL_PREFILTER_COUNT)
                )
                expanded_matched = list((await db.execute(stmt_expanded_match)).scalars().all())
                if expanded_matched:
                    candidates = [(h, True) for h in expanded_matched]
                else:
                    stmt_expanded_gen = (
                        select(Hospital)
                        .where(Hospital.has_emergency.is_(True))
                        .order_by(distance_expr.asc())
                        .limit(settings.HOSPITAL_PREFILTER_COUNT)
                    )
                    candidates = [(h, False) for h in (await db.execute(stmt_expanded_gen)).scalars().all()]
            else:
                stmt_expanded_all = (
                    select(Hospital)
                    .where(Hospital.has_emergency.is_(True))
                    .order_by(distance_expr.asc())
                    .limit(settings.HOSPITAL_PREFILTER_COUNT)
                )
                candidates = [(h, True) for h in (await db.execute(stmt_expanded_all)).scalars().all()]

        if not candidates:
            empty_resp = HospitalNearbyResponse(hospitals=[])
            cache.set(cache_key, empty_resp, ttl_seconds=30)
            return empty_resp

        # Calculate ETAs: instant distance-based estimation for all candidates
        evaluated_hospitals: List[HospitalNearbyItem] = []

        for h, matches in candidates:
            h_lat, h_lng = extract_incident_lat_lng(h.location)
            # Estimate urban road distance (~1.35x haversine) and urban emergency speed (~25 km/h = 6.94 m/s)
            straight_line = haversine_distance_m(origin_lat, origin_lng, h_lat, h_lng)
            est_road_dist = round(straight_line * 1.35, 1)
            est_eta_s = round(est_road_dist / 6.94, 1)

            evaluated_hospitals.append(
                HospitalNearbyItem(
                    id=h.id,
                    name=h.name,
                    lat=h_lat,
                    lng=h_lng,
                    phone=h.phone,
                    address=h.address,
                    eta_s=est_eta_s,
                    distance_m=est_road_dist,
                    matches_type=matches,
                    simulated_beds=h.simulated_beds,
                    beds_simulated=True,
                    eta_estimated=True,
                    route_geometry=None,
                )
            )

        # Rank candidates by initial ETA
        ranked = sorted(evaluated_hospitals, key=lambda x: x.eta_s)

        # For the top 1 closest candidate, attempt full turn-by-turn routing with a strict 2s timeout
        if ranked:
            best_candidate = ranked[0]
            try:
                route_task = routing_service.get_routes(
                    origin=origin,
                    destination=(best_candidate.lat, best_candidate.lng),
                    use_incidents=True,
                    db=db,
                )
                route_resp = await asyncio.wait_for(route_task, timeout=2.0)
                if route_resp and route_resp.routes:
                    best_route = route_resp.routes[0]
                    best_candidate.eta_s = best_route.adjusted_duration_s or best_route.duration_s
                    best_candidate.distance_m = best_route.distance_m
                    best_candidate.route_geometry = best_route.geometry
                    best_candidate.eta_estimated = False
            except Exception as exc:
                logger.debug("Quick routing timed out or failed for %s (%s). Using estimate.", best_candidate.name, exc)

        # Ensure only the top hospital retains route_geometry to keep payload compact
        for i, item in enumerate(ranked):
            if i > 0:
                item.route_geometry = None

        response = HospitalNearbyResponse(
            emergency_number=settings.EMERGENCY_NUMBER,
            disclaimer="Suggestions only, not medical advice. Bed numbers are simulated.",
            hospitals=ranked,
        )

        cache.set(cache_key, response, ttl_seconds=30)
        return response


hospital_service = HospitalService()
