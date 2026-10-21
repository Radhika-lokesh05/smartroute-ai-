"""
Emergency ambulance dispatching service.
Finds nearest verified, available ambulances within DISPATCH_CANDIDATE_RADIUS_M,
calculates routing ETAs for top candidates, offers dispatches sequentially,
enforces offer timeouts, and handles state progression.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from geoalchemy2.functions import ST_Distance, ST_DWithin
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.ambulance import Ambulance, AmbulanceStatus
from app.models.dispatch import ACTIVE_DISPATCH_STATUSES, Dispatch, DispatchStatus
from app.models.hospital import Hospital
from app.models.incident import Incident, IncidentStatus
from app.services.incident_service import extract_incident_lat_lng
from app.services.realtime import haversine_distance_m, realtime_manager
from app.services.routing_service import routing_service

logger = logging.getLogger("smartroute.dispatch")


class DispatchService:
    """Manages ambulance dispatch lifecycle, candidate selection, and offer routing."""

    async def trigger_dispatch(
        self,
        incident_id: uuid.UUID,
        db: AsyncSession,
        emergency_type: str = "general",
    ) -> Optional[Dispatch]:
        """
        Trigger emergency dispatch for an active incident.
        1. Verifies incident is active and has no open dispatch.
        2. Queries verified, available ambulances within DISPATCH_CANDIDATE_RADIUS_M.
        3. Excludes ambulances that previously declined or expired on this incident.
        4. Calculates traffic-aware routing ETAs for top candidates.
        5. Issues offer to fastest candidate and notifies ambulance via WebSocket.
        """
        # Fetch incident
        stmt_inc = select(Incident).where(Incident.id == incident_id)
        res_inc = await db.execute(stmt_inc)
        incident = res_inc.scalar_one_or_none()

        if not incident or incident.status in (IncidentStatus.resolved, IncidentStatus.expired):
            logger.warning("Cannot dispatch: incident %s is non-existent or inactive.", incident_id)
            return None

        # Check for existing open dispatch
        stmt_active = (
            select(Dispatch)
            .where(Dispatch.incident_id == incident_id)
            .where(Dispatch.status.in_(list(ACTIVE_DISPATCH_STATUSES)))
        )
        res_active = await db.execute(stmt_active)
        existing_active = res_active.scalar_one_or_none()
        if existing_active:
            logger.info("Active dispatch %s already exists for incident %s", existing_active.id, incident_id)
            return existing_active

        # Count total previous offers for this incident
        stmt_offers = select(Dispatch).where(Dispatch.incident_id == incident_id)
        res_offers = await db.execute(stmt_offers)
        past_dispatches = list(res_offers.scalars().all())
        offer_count = len(past_dispatches)

        if offer_count >= settings.DISPATCH_MAX_OFFERS_PER_INCIDENT:
            logger.warning("Incident %s has reached max offers (%d); aborting automated dispatch.", incident_id, offer_count)
            return None

        # Exclude ambulances that previously declined or expired for this incident
        excluded_amb_ids = {d.ambulance_id for d in past_dispatches}

        # Query candidates within radius
        distance_expr = ST_Distance(Ambulance.last_location, incident.location)
        stmt_candidates = (
            select(Ambulance)
            .where(Ambulance.is_verified.is_(True))
            .where(Ambulance.status == AmbulanceStatus.available)
            .where(Ambulance.last_location.is_not(None))
            .where(ST_DWithin(Ambulance.last_location, incident.location, settings.DISPATCH_CANDIDATE_RADIUS_M))
            .order_by(distance_expr.asc())
        )
        res_candidates = await db.execute(stmt_candidates)
        all_candidates = [a for a in res_candidates.scalars().all() if a.id not in excluded_amb_ids]

        if not all_candidates:
            logger.info("No available, verified candidate ambulances within %dm for incident %s", int(settings.DISPATCH_CANDIDATE_RADIUS_M), incident_id)
            return None

        inc_lat, inc_lng = extract_incident_lat_lng(incident.location)

        # Evaluate real route ETAs for top DISPATCH_CANDIDATE_ROUTE_COUNT candidates
        evaluated_candidates: List[Tuple[Ambulance, float]] = []

        for idx, amb in enumerate(all_candidates[: settings.DISPATCH_CANDIDATE_ROUTE_COUNT]):
            amb_lat, amb_lng = extract_incident_lat_lng(amb.last_location)
            try:
                route_res = await routing_service.get_routes(
                    origin=(amb_lat, amb_lng),
                    destination=(inc_lat, inc_lng),
                    use_incidents=True,
                    db=db,
                )
                if route_res.routes:
                    best_route = route_res.routes[0]
                    eta_s = best_route.adjusted_duration_s or best_route.duration_s
                else:
                    raise ValueError("No route found")
            except Exception as exc:
                logger.warning("Routing to incident failed for ambulance %s: %s; using straight-line ETA.", amb.id, exc)
                dist_m = haversine_distance_m(amb_lat, amb_lng, inc_lat, inc_lng)
                eta_s = round(dist_m / 11.1, 1)  # ~40 km/h emergency speed

            evaluated_candidates.append((amb, eta_s))

        # Select the fastest ambulance candidate
        evaluated_candidates.sort(key=lambda x: x[1])
        chosen_amb, chosen_eta = evaluated_candidates[0]

        new_dispatch = Dispatch(
            incident_id=incident_id,
            ambulance_id=chosen_amb.id,
            status=DispatchStatus.offered,
            offered_at=datetime.now(timezone.utc),
            eta_to_scene_s=chosen_eta,
            emergency_type=emergency_type,
            offer_number=offer_count + 1,
            is_simulated=bool(incident.is_simulated),
        )
        db.add(new_dispatch)
        await db.commit()
        await db.refresh(new_dispatch)

        # Notify ambulance over WebSocket
        await realtime_manager.send_to_user(
            str(chosen_amb.user_id),
            {
                "v": 1,
                "type": "dispatch.offered",
                "data": {
                    "dispatch_id": str(new_dispatch.id),
                    "incident_id": str(incident_id),
                    "emergency_type": emergency_type,
                    "eta_to_scene_s": chosen_eta,
                    "offer_number": new_dispatch.offer_number,
                    "expires_in_s": int(settings.DISPATCH_OFFER_TIMEOUT_S),
                },
            },
        )

        logger.info("Offered dispatch %s to ambulance %s (offer %d, ETA: %.1fs)", new_dispatch.id, chosen_amb.id, new_dispatch.offer_number, chosen_eta)
        return new_dispatch

    async def accept_dispatch(self, dispatch_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Dispatch:
        """Ambulance operator accepts dispatch offer. Sets status=en_route_to_scene and ambulance.status=busy."""
        stmt = (
            select(Dispatch)
            .where(Dispatch.id == dispatch_id)
            .options(selectinload(Dispatch.ambulance))
        )
        res = await db.execute(stmt)
        dispatch = res.scalar_one_or_none()

        if not dispatch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispatch not found.")

        if dispatch.ambulance.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dispatch is not assigned to your vehicle.")

        if dispatch.status != DispatchStatus.offered:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot accept dispatch with status '{dispatch.status.value}'.",
            )

        now = datetime.now(timezone.utc)
        dispatch.status = DispatchStatus.en_route_to_scene
        dispatch.accepted_at = now
        dispatch.ambulance.status = AmbulanceStatus.busy

        await db.commit()
        await db.refresh(dispatch)

        # Notify ambulance and admins
        accepted_msg = {
            "v": 1,
            "type": "dispatch.accepted",
            "data": {
                "dispatch_id": str(dispatch.id),
                "incident_id": str(dispatch.incident_id),
                "ambulance_id": str(dispatch.ambulance_id),
                "accepted_at": now.isoformat(),
            },
        }
        await realtime_manager.send_to_user(str(user_id), accepted_msg)
        await realtime_manager.send_to_role("admin", accepted_msg)

        logger.info("Ambulance %s accepted dispatch %s", dispatch.ambulance_id, dispatch.id)
        return dispatch

    async def decline_dispatch(
        self,
        dispatch_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
        reason: Optional[str] = None,
    ) -> Dispatch:
        """Ambulance operator declines dispatch offer. Automatically re-triggers next offer if available."""
        stmt = (
            select(Dispatch)
            .where(Dispatch.id == dispatch_id)
            .options(selectinload(Dispatch.ambulance))
        )
        res = await db.execute(stmt)
        dispatch = res.scalar_one_or_none()

        if not dispatch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispatch not found.")

        if dispatch.ambulance.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dispatch is not assigned to your vehicle.")

        if dispatch.status != DispatchStatus.offered:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot decline dispatch with status '{dispatch.status.value}'.",
            )

        dispatch.status = DispatchStatus.declined
        await db.commit()
        await db.refresh(dispatch)

        logger.info("Ambulance %s declined dispatch %s (reason: %s). Offering to next candidate...", dispatch.ambulance_id, dispatch.id, reason)

        # Automatically attempt next offer
        if dispatch.offer_number < settings.DISPATCH_MAX_OFFERS_PER_INCIDENT:
            await self.trigger_dispatch(dispatch.incident_id, db, dispatch.emergency_type)

        return dispatch

    async def update_progress(
        self,
        dispatch_id: uuid.UUID,
        user_id: uuid.UUID,
        new_status: str,
        hospital_id: Optional[uuid.UUID],
        db: AsyncSession,
    ) -> Dispatch:
        """Advance dispatch status (at_scene, to_hospital, completed, cancelled)."""
        stmt = (
            select(Dispatch)
            .where(Dispatch.id == dispatch_id)
            .options(selectinload(Dispatch.ambulance), selectinload(Dispatch.incident))
        )
        res = await db.execute(stmt)
        dispatch = res.scalar_one_or_none()

        if not dispatch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispatch not found.")

        if dispatch.ambulance.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dispatch is not assigned to your vehicle.")

        now = datetime.now(timezone.utc)
        clean_status = new_status.strip().lower()

        if clean_status == "at_scene":
            if dispatch.status != DispatchStatus.en_route_to_scene:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must be en_route_to_scene to arrive at scene.")
            dispatch.status = DispatchStatus.at_scene
            dispatch.arrived_at = now

        elif clean_status == "to_hospital":
            if dispatch.status not in (DispatchStatus.at_scene, DispatchStatus.en_route_to_scene):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot transition to_hospital from current status.")
            dispatch.status = DispatchStatus.to_hospital
            dispatch.picked_up_at = now
            if hospital_id:
                dispatch.hospital_id = hospital_id
                # Calculate routing ETA to hospital
                stmt_hosp = select(Hospital).where(Hospital.id == hospital_id)
                res_hosp = await db.execute(stmt_hosp)
                hosp = res_hosp.scalar_one_or_none()
                if hosp and dispatch.incident:
                    try:
                        inc_lat, inc_lng = extract_incident_lat_lng(dispatch.incident.location)
                        h_lat, h_lng = extract_incident_lat_lng(hosp.location)
                        h_route = await routing_service.get_routes(origin=(inc_lat, inc_lng), destination=(h_lat, h_lng), use_incidents=True, db=db)
                        if h_route.routes:
                            dispatch.eta_to_hospital_s = h_route.routes[0].adjusted_duration_s or h_route.routes[0].duration_s
                    except Exception as exc:
                        logger.warning("Routing to destination hospital %s failed: %s", hospital_id, exc)

        elif clean_status == "completed":
            dispatch.status = DispatchStatus.completed
            dispatch.completed_at = now
            dispatch.ambulance.status = AmbulanceStatus.available

        elif clean_status == "cancelled":
            dispatch.status = DispatchStatus.cancelled
            dispatch.ambulance.status = AmbulanceStatus.available

        else:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid progress status '{new_status}'.")

        await db.commit()
        await db.refresh(dispatch)

        # Notify ambulance and admins
        updated_msg = {
            "v": 1,
            "type": "dispatch.updated",
            "data": {
                "dispatch_id": str(dispatch.id),
                "status": dispatch.status.value,
                "hospital_id": str(dispatch.hospital_id) if dispatch.hospital_id else None,
                "timestamp": now.isoformat(),
            },
        }
        await realtime_manager.send_to_user(str(user_id), updated_msg)
        await realtime_manager.send_to_role("admin", updated_msg)

        # Emit hospital.prealert when en route to hospital
        if clean_status == "to_hospital" and dispatch.hospital_id:
            prealert_msg = {
                "v": 1,
                "type": "hospital.prealert",
                "data": {
                    "dispatch_id": str(dispatch.id),
                    "hospital_id": str(dispatch.hospital_id),
                    "eta_s": round(dispatch.eta_to_hospital_s, 1),
                    "emergency_type": dispatch.emergency_type,
                },
            }
            await realtime_manager.send_to_role("admin", prealert_msg)
            if dispatch.incident and dispatch.incident.location:
                try:
                    inc_lat, inc_lng = extract_incident_lat_lng(dispatch.incident.location)
                    await realtime_manager.broadcast_to_area(inc_lat, inc_lng, prealert_msg)
                except Exception:
                    pass

        return dispatch

    async def sweep_expired_offers(self, db: AsyncSession) -> None:
        """Expire unaccepted offers exceeding DISPATCH_OFFER_TIMEOUT_S and offer to next candidate."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(Dispatch)
            .where(Dispatch.status == DispatchStatus.offered)
        )
        res = await db.execute(stmt)
        open_offers = list(res.scalars().all())

        for offer in open_offers:
            elapsed_s = (now - offer.offered_at).total_seconds()
            if elapsed_s > settings.DISPATCH_OFFER_TIMEOUT_S:
                offer.status = DispatchStatus.expired
                await db.commit()
                logger.info("Dispatch offer %s expired after %.1fs. Checking for next candidate...", offer.id, elapsed_s)
                if offer.offer_number < settings.DISPATCH_MAX_OFFERS_PER_INCIDENT:
                    await self.trigger_dispatch(offer.incident_id, db, offer.emergency_type)


dispatch_service = DispatchService()
