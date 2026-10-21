import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx
from datetime import datetime, timezone
from app.core.config import settings
from app.core.cache import cache, make_route_cache_key
from app.services.ors_client import (
    ors_client,
    ORSError,
    ORSNoRouteError,
    ORSProviderError,
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.routing import (
    RouteResponse,
    RouteItem,
    RouteStep,
    RouteSummary,
    RouteTrafficSummary,
    GeoJSONLineString,
)
from app.services.incident_routing import (
    are_routes_near_duplicates,
    build_avoid_multipolygon,
    find_incidents_on_route,
    generate_route_reason,
    get_active_corridor_incidents,
    hash_incidents_state,
)
from app.services.traffic_model import traffic_model_service
from app.services.weather_service import weather_service

logger = logging.getLogger(__name__)

# Approximate geographic bounding box for India (Mainland + Islands)
INDIA_MIN_LAT, INDIA_MAX_LAT = 6.0, 38.0
INDIA_MIN_LNG, INDIA_MAX_LNG = 68.0, 98.0


def is_within_india(lat: float, lng: float) -> bool:
    """Check if point falls within the approximate boundary of India."""
    return INDIA_MIN_LAT <= lat <= INDIA_MAX_LAT and INDIA_MIN_LNG <= lng <= INDIA_MAX_LNG


def check_india_warning(from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> Optional[str]:
    """Return advisory warning if coordinates are outside India without failing."""
    if not (is_within_india(from_lat, from_lng) and is_within_india(to_lat, to_lng)):
        return "Advisory: Coordinates are outside the primary India service region."
    return None


class RoutingService:
    """Service orchestrating multi-alternative car routing with incident awareness and OSRM fallback."""

    def __init__(self, client=ors_client) -> None:
        self.client = client

    async def get_raw_routes(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        avoid_polygons: Optional[Dict[str, Any]] = None,
    ) -> RouteResponse:
        """Query raw driving route candidates from OpenRouteService or OSRM fallback."""
        origin_lat, origin_lng = origin
        dest_lat, dest_lng = destination
        warning = check_india_warning(origin_lat, origin_lng, dest_lat, dest_lng)

        payload: Dict[str, Any] = {
            "coordinates": [
                [origin_lng, origin_lat],
                [dest_lng, dest_lat],
            ],
            "alternative_routes": {
                "target_count": 3,
            },
        }

        if avoid_polygons:
            payload["options"] = {"avoid_polygons": avoid_polygons}

        try:
            raw_data = await self.client.request(
                method="POST",
                path_or_url=settings.ORS_DIRECTIONS_PATH,
                json_data=payload,
            )
            return self._parse_ors_response(raw_data, warning=warning)
        except ORSError as exc:
            logger.warning("OpenRouteService failed: %s", exc)
            if settings.ROUTING_FALLBACK_ENABLED:
                logger.info("ROUTING_FALLBACK_ENABLED is active. Falling back to OSRM demo server.")
                return await self._fetch_osrm_fallback(origin, destination, warning=warning)
            raise
        except Exception as exc:
            logger.error("Unexpected error in route calculation: %s", exc)
            if settings.ROUTING_FALLBACK_ENABLED:
                return await self._fetch_osrm_fallback(origin, destination, warning=warning)
            raise ORSProviderError(f"Route calculation failed: {type(exc).__name__}") from exc

    async def get_routes(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        avoid_polygons: Optional[Dict[str, Any]] = None,
        use_incidents: bool = True,
        db: Optional[AsyncSession] = None,
        departure_time: Optional[datetime] = None,
    ) -> RouteResponse:
        """
        Compute up to 4 ranked driving routes between origin and destination.
        Evaluates road incidents within INCIDENT_ROUTE_BUFFER_M, applies delay penalties,
        incorporates ML traffic congestion predictions & weather conditions,
        generates avoid-candidate alternatives, and ranks by adjusted duration.
        """
        origin_lat, origin_lng = origin
        dest_lat, dest_lng = destination

        if departure_time is None:
            departure_time = datetime.now(timezone.utc)
        elif departure_time.tzinfo is None:
            departure_time = departure_time.replace(tzinfo=timezone.utc)

        # Midpoint for weather fetch
        mid_lat = (origin_lat + dest_lat) / 2.0
        mid_lng = (origin_lng + dest_lng) / 2.0
        weather = await weather_service.get_weather(mid_lat, mid_lng, at_time=departure_time)
        weather_condition = weather.condition if weather else "Clear"

        corridor_incidents = []
        inc_hash = "none"
        if use_incidents and db is not None:
            corridor_incidents = await get_active_corridor_incidents(db, origin, destination)
            inc_hash = hash_incidents_state(corridor_incidents)
        elif not use_incidents:
            inc_hash = "disabled"

        # Check in-memory cache
        date_bucket = departure_time.strftime("%Y-%m-%d")
        cache_key = make_route_cache_key(
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            avoid_polygons,
            incidents_hash=inc_hash,
            model_version=traffic_model_service.model_version,
            date_bucket=date_bucket,
            weather_condition=weather_condition,
        )
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.info("Serving route calculation from in-memory cache: %s", cache_key)
            return cached_result

        # Request initial route candidates
        raw_response = await self.get_raw_routes(origin, destination, avoid_polygons=avoid_polygons)
        candidate_routes = [r.model_copy(deep=True) for r in raw_response.routes]

        traffic_summary = RouteTrafficSummary(
            model_version=traffic_model_service.model_version,
            data_source=traffic_model_service.data_source,
            data_granularity=traffic_model_service.data_granularity,
            time_of_day_modelled=False,
            model_available=traffic_model_service.model_available,
            weather=weather,
        )

        def apply_route_metrics(r: RouteItem, delay_s: float, inc_list: list):
            r.incidents_on_route = inc_list
            r.estimated_delay_s = delay_s
            factor, coverage = traffic_model_service.calculate_route_traffic(
                r.geometry.coordinates,
                when=departure_time,
                weather=weather_condition,
            )
            r.traffic_factor = factor
            r.traffic_coverage = coverage
            r.predicted_duration_s = round(r.duration_s * factor, 1)
            # DO NOT double-count: incident delays are added on top of traffic-predicted duration
            r.adjusted_duration_s = round(r.predicted_duration_s + delay_s, 1)
            r.avoids_incidents = bool(avoid_polygons)

        # If incident evaluation is disabled or no incidents exist, return base routes
        if not use_incidents or not corridor_incidents:
            for r in candidate_routes:
                apply_route_metrics(r, delay_s=0.0, inc_list=[])

            ranked_routes = sorted(candidate_routes, key=lambda r: r.adjusted_duration_s)[:4]
            raw_fastest = min(ranked_routes, key=lambda r: r.duration_s)
            raw_fastest_adj = raw_fastest.adjusted_duration_s

            for idx, r in enumerate(ranked_routes):
                r.rank = idx + 1
                if not use_incidents:
                    traffic_factor = getattr(r, "traffic_factor", 1.0)
                    if traffic_factor > 1.05:
                        pct = int(round((traffic_factor - 1.0) * 100))
                        r.reason = (
                            f"Fastest route, ~{pct}% slower than free-flow due to predicted traffic"
                            if idx == 0
                            else f"~{pct}% slower than free-flow due to predicted traffic"
                        )
                    else:
                        r.reason = "Incident evaluation disabled"
                else:
                    r.reason = generate_route_reason(r, r.rank, raw_fastest_adj, 0)

            summary = RouteSummary(
                incidents_considered=len(corridor_incidents),
                fastest_raw_route_index=0,
                recommended_route_index=0,
                rerouted=False,
            )
            response = RouteResponse(
                provider=raw_response.provider,
                warning=raw_response.warning,
                summary=summary,
                traffic=traffic_summary,
                routes=ranked_routes,
            )
            cache.set(cache_key, response, ttl_seconds=settings.CACHE_TTL_SECONDS)
            return response

        # Evaluate incidents and traffic on each candidate route
        for r in candidate_routes:
            incidents_on_r, delay_s = find_incidents_on_route(
                r.geometry.coordinates,
                corridor_incidents,
                settings.INCIDENT_ROUTE_BUFFER_M,
            )
            apply_route_metrics(r, delay_s=delay_s, inc_list=incidents_on_r)

        # Identify fastest raw candidate and check for validated incidents
        raw_fastest_route = min(candidate_routes, key=lambda r: r.duration_s)
        raw_fastest_adj = raw_fastest_route.adjusted_duration_s
        validated_on_fastest = [inc for inc in raw_fastest_route.incidents_on_route if inc.status == "validated"]

        # Build avoid candidate if validated incidents lie on the fastest route
        if validated_on_fastest and not avoid_polygons:
            avoid_multipoly = build_avoid_multipolygon(
                validated_incidents_on_fastest=validated_on_fastest,
                origin=origin,
                destination=destination,
                radius_m=settings.AVOID_POLYGON_RADIUS_M,
                max_count=settings.MAX_AVOID_INCIDENTS,
            )
            if avoid_multipoly:
                try:
                    avoid_response = await self.get_raw_routes(
                        origin=origin,
                        destination=destination,
                        avoid_polygons=avoid_multipoly,
                    )
                    if avoid_response.routes:
                        avoid_candidate = avoid_response.routes[0].model_copy(deep=True)
                        avoid_candidate.avoids_incidents = True
                        inc_on_avoid, delay_avoid = find_incidents_on_route(
                            avoid_candidate.geometry.coordinates,
                            corridor_incidents,
                            settings.INCIDENT_ROUTE_BUFFER_M,
                        )
                        apply_route_metrics(avoid_candidate, delay_s=delay_avoid, inc_list=inc_on_avoid)
                        avoid_candidate.avoids_incidents = True
                        candidate_routes.append(avoid_candidate)
                except Exception as exc:
                    logger.warning("Could not calculate avoid candidate route: %s. Continuing with normal alternatives.", exc)

        # Deduplicate near-duplicates
        unique_candidates: List[RouteItem] = []
        for cand in candidate_routes:
            dup_match = next((u for u in unique_candidates if are_routes_near_duplicates(cand, u)), None)
            if dup_match is not None:
                if (cand.avoids_incidents and not dup_match.avoids_incidents) or cand.adjusted_duration_s < dup_match.adjusted_duration_s:
                    unique_candidates.remove(dup_match)
                    unique_candidates.append(cand)
            else:
                unique_candidates.append(cand)

        # Rank by adjusted duration (estimated ETA)
        ranked_routes = sorted(unique_candidates, key=lambda r: r.adjusted_duration_s)[:4]
        for idx, r in enumerate(ranked_routes):
            r.rank = idx + 1
            r.reason = generate_route_reason(r, r.rank, raw_fastest_adj, len(validated_on_fastest))

        fastest_raw_index = min(range(len(ranked_routes)), key=lambda idx: ranked_routes[idx].duration_s)
        recommended_index = 0
        rerouted = (fastest_raw_index != recommended_index) and len(corridor_incidents) > 0

        summary = RouteSummary(
            incidents_considered=len(corridor_incidents),
            fastest_raw_route_index=fastest_raw_index,
            recommended_route_index=recommended_index,
            rerouted=rerouted,
        )

        response = RouteResponse(
            provider=raw_response.provider,
            warning=raw_response.warning,
            summary=summary,
            traffic=traffic_summary,
            routes=ranked_routes,
        )

        ttl = settings.ROUTE_CACHE_TTL_WITH_INCIDENTS_S if corridor_incidents else settings.CACHE_TTL_SECONDS
        cache.set(cache_key, response, ttl_seconds=ttl)
        return response

    def _parse_ors_response(self, data: Dict[str, Any], warning: Optional[str] = None) -> RouteResponse:
        """Parse GeoJSON FeatureCollection returned by OpenRouteService."""
        routes: List[RouteItem] = []

        # When requesting geojson, ORS returns FeatureCollection
        features = data.get("features", [])
        if not features and "routes" in data:
            # Handle standard JSON format fallback
            return self._parse_ors_json_routes(data["routes"], warning)

        if not features:
            raise ORSNoRouteError("No route returned by OpenRouteService")

        for feature in features[:3]:
            geom_data = feature.get("geometry", {})
            coords = geom_data.get("coordinates", [])
            props = feature.get("properties", {})
            summary = props.get("summary", {})

            # Extract turn-by-turn navigation steps
            steps: List[RouteStep] = []
            for segment in props.get("segments", []):
                for st in segment.get("steps", []):
                    steps.append(
                        RouteStep(
                            instruction=st.get("instruction", ""),
                            distance_m=float(st.get("distance", 0.0)),
                            duration_s=float(st.get("duration", 0.0)),
                            name=st.get("name", "") or "",
                            maneuver_type=str(st.get("type", "maneuver")),
                        )
                    )

            routes.append(
                RouteItem(
                    distance_m=float(summary.get("distance", 0.0)),
                    duration_s=float(summary.get("duration", 0.0)),
                    geometry=GeoJSONLineString(coordinates=coords),
                    steps=steps,
                )
            )

        return RouteResponse(
            provider="openrouteservice",
            warning=warning,
            routes=routes,
        )

    def _parse_ors_json_routes(self, raw_routes: List[Dict[str, Any]], warning: Optional[str] = None) -> RouteResponse:
        """Parse non-GeoJSON ORS routes array if returned."""
        routes: List[RouteItem] = []
        for r in raw_routes[:3]:
            summary = r.get("summary", {})
            geom = r.get("geometry", {})
            coords = geom if isinstance(geom, list) else geom.get("coordinates", [])
            steps: List[RouteStep] = []
            for seg in r.get("segments", []):
                for st in seg.get("steps", []):
                    steps.append(
                        RouteStep(
                            instruction=st.get("instruction", ""),
                            distance_m=float(st.get("distance", 0.0)),
                            duration_s=float(st.get("duration", 0.0)),
                            name=st.get("name", "") or "",
                            maneuver_type=str(st.get("type", "maneuver")),
                        )
                    )
            routes.append(
                RouteItem(
                    distance_m=float(summary.get("distance", 0.0)),
                    duration_s=float(summary.get("duration", 0.0)),
                    geometry=GeoJSONLineString(coordinates=coords),
                    steps=steps,
                )
            )
        return RouteResponse(provider="openrouteservice", warning=warning, routes=routes)

    async def _fetch_osrm_fallback(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        warning: Optional[str] = None,
    ) -> RouteResponse:
        """Query public OSRM demo server when ORS is unreachable and fallback is enabled."""
        origin_lat, origin_lng = origin
        dest_lat, dest_lng = destination

        base = settings.OSRM_BASE_URL.rstrip("/")
        path = settings.OSRM_DIRECTIONS_PATH.rstrip("/")
        url = f"{base}{path}/{origin_lng},{origin_lat};{dest_lng},{dest_lat}"

        params = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "true",
            "alternatives": "true",
        }

        data = await self._call_osrm_api(url, params)

        if data.get("code") != "Ok" or not data.get("routes"):
            raise ORSNoRouteError("No route returned by OSRM fallback server")

        routes: List[RouteItem] = []
        for r in data["routes"][:3]:
            coords = r.get("geometry", {}).get("coordinates", [])
            steps: List[RouteStep] = []
            for leg in r.get("legs", []):
                for st in leg.get("steps", []):
                    maneuver = st.get("maneuver", {})
                    maneuver_type = f"{maneuver.get('type', '')} {maneuver.get('modifier', '')}".strip() or "turn"
                    steps.append(
                        RouteStep(
                            instruction=st.get("name", "") or maneuver_type,
                            distance_m=float(st.get("distance", 0.0)),
                            duration_s=float(st.get("duration", 0.0)),
                            name=st.get("name", "") or "",
                            maneuver_type=maneuver_type,
                        )
                    )

            routes.append(
                RouteItem(
                    distance_m=float(r.get("distance", 0.0)),
                    duration_s=float(r.get("duration", 0.0)),
                    geometry=GeoJSONLineString(coordinates=coords),
                    steps=steps,
                )
            )

        return RouteResponse(
            provider="osrm-demo",
            warning=warning or "Using secondary public OSRM routing fallback.",
            routes=routes,
        )

    async def _call_osrm_api(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HTTP request against OSRM server."""
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            resp = await http_client.get(url, params=params)
            if resp.status_code != 200:
                raise ORSProviderError(f"OSRM fallback server returned error {resp.status_code}")
            return resp.json()


routing_service = RoutingService()
