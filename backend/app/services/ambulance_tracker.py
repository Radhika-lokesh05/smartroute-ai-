"""
Ambulance live tracking, speed jump validation, and civilian proximity warning service.

NOTE: In-memory tracker behind a clean interface. In a distributed multi-worker deployment,
this state can be seamlessly backed by Redis or an external geocache.
"""
import asyncio
import logging
import math
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Set, Tuple
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ambulance import Ambulance, AmbulanceStatus
from app.models.dispatch import Dispatch, DispatchStatus
from app.services.realtime import haversine_distance_m, realtime_manager

logger = logging.getLogger("smartroute.ambulance_tracker")


def calculate_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate initial great-circle bearing from point 1 to point 2 in degrees [0, 360)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360.0) % 360.0


class AmbulanceTrackerState:
    def __init__(self, ambulance_id: str, user_id: str) -> None:
        self.ambulance_id = ambulance_id
        self.user_id = user_id
        self.lat: float = 0.0
        self.lng: float = 0.0
        self.heading: float = 0.0
        self.speed: float = 0.0
        self.updated_at: float = 0.0
        self.history: Deque[Tuple[float, float, float]] = deque(maxlen=5)  # (lat, lng, timestamp)
        self.last_db_flush: float = 0.0
        self.warned_civilians: Dict[Any, float] = {}  # websocket -> timestamp


class AmbulanceTrackerService:
    """
    Manages in-memory live tracking of ambulances, speed validation,
    periodic DB flushing, and throttled civilian proximity alerts.
    """

    def __init__(self) -> None:
        self._states: Dict[str, AmbulanceTrackerState] = {}
        self._lock = asyncio.Lock()

    def get_ambulance_state(self, ambulance_id: str) -> Optional[AmbulanceTrackerState]:
        return self._states.get(str(ambulance_id))

    def clear(self) -> None:
        """Clear all in-memory tracker states (used in tests)."""
        self._states.clear()

    async def process_location_update(
        self,
        ambulance: Optional[Any] = None,
        user: Optional[Any] = None,
        user_id: Optional[str] = None,
        lat: float = 0.0,
        lng: float = 0.0,
        heading: float = 0.0,
        speed: float = 0.0,
        db: Optional[AsyncSession] = None,
    ) -> bool:
        """Alias for update_location accepting model objects or IDs."""
        u_id = str(user.id if user else (ambulance.user_id if ambulance else user_id))
        return await self.update_location(
            user_id=u_id,
            lat=lat,
            lng=lng,
            heading=heading,
            speed=speed,
            db=db,
        )

    async def update_location(
        self,
        user_id: str,
        lat: float,
        lng: float,
        heading: float,
        speed: float,
        db: AsyncSession,
    ) -> bool:
        """
        Process and validate incoming ambulance location update.
        1. Validates coordinate and value ranges.
        2. Drops updates faster than AMBULANCE_LOCATION_MIN_INTERVAL_S.
        3. Rejects telematics jumps exceeding 150 km/h.
        4. Periodically flushes to PostGIS DB.
        5. Forwards location strictly to ambulance user and admins.
        6. Emits proximity warning to nearby civilians only during active dispatch.
        """
        # Validate ranges
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
            return False
        if not (0.0 <= heading <= 360.0 and 0.0 <= speed <= 150.0):
            return False

        now = time.time()

        # Query ambulance from DB
        stmt = select(Ambulance).where(Ambulance.user_id == user_id)
        res = await db.execute(stmt)
        ambulance = res.scalar_one_or_none()

        if not ambulance or not ambulance.is_verified:
            logger.warning("Unverified or non-existent ambulance for user %s attempted location update.", user_id)
            return False

        amb_id_str = str(ambulance.id)

        async with self._lock:
            state = self._states.get(amb_id_str)
            if not state:
                state = AmbulanceTrackerState(amb_id_str, user_id)
                self._states[amb_id_str] = state

            # Rate limiting / minimum interval check
            if state.updated_at > 0 and (now - state.updated_at) < settings.AMBULANCE_LOCATION_MIN_INTERVAL_S:
                return False

            # Speed jump check (impossible movement > 150 km/h)
            if state.updated_at > 0:
                dt = now - state.updated_at
                if dt > 0:
                    dist_m = haversine_distance_m(state.lat, state.lng, lat, lng)
                    implied_speed_kmh = (dist_m / dt) * 3.6
                    if implied_speed_kmh > 150.0:
                        logger.warning(
                            "Ambulance %s location jump exceeds 150 km/h (%.1f km/h); dropping update",
                            amb_id_str,
                            implied_speed_kmh,
                        )
                        return False

            # Update memory state
            state.lat = lat
            state.lng = lng
            state.heading = heading
            state.speed = speed
            state.updated_at = now
            state.history.append((lat, lng, now))

            # DB Flush check
            if (now - state.last_db_flush) >= settings.AMBULANCE_DB_FLUSH_S:
                ambulance.last_location = WKTElement(f"POINT({lng} {lat})", srid=4326)
                ambulance.last_seen_at = datetime.now(timezone.utc)
                await db.commit()
                state.last_db_flush = now

        # Privacy: Location messages go only to: (a) that ambulance's own user, (b) admins.
        location_msg = {
            "v": 1,
            "type": "ambulance.location",
            "data": {
                "ambulance_id": amb_id_str,
                "lat": lat,
                "lng": lng,
                "heading": heading,
                "speed": speed,
                "status": ambulance.status.value,
            },
        }
        await realtime_manager.send_to_user(user_id, location_msg)
        await realtime_manager.send_to_role("admin", location_msg)

        # Proximity Warning: ONLY while ambulance has an active dispatch (status busy and en route)
        await self._process_proximity_warning(ambulance, state, lat, lng, speed, db, now)

        return True

    async def _process_proximity_warning(
        self,
        ambulance: Ambulance,
        state: AmbulanceTrackerState,
        lat: float,
        lng: float,
        speed: float,
        db: AsyncSession,
        now: float,
    ) -> None:
        """
        Send proximity warning ONLY when ambulance is busy on an active dispatch.
        Throttled to CIVILIAN_WARN_MIN_INTERVAL_S per civilian connection.
        """
        is_active_dispatch = False
        if ambulance.status == AmbulanceStatus.busy:
            stmt = (
                select(Dispatch)
                .where(Dispatch.ambulance_id == ambulance.id)
                .where(Dispatch.status.in_([DispatchStatus.en_route_to_scene, DispatchStatus.to_hospital]))
            )
            res = await db.execute(stmt)
            if res.scalar_one_or_none() is not None:
                is_active_dispatch = True

        if not is_active_dispatch:
            # Clear any previously warned civilians
            if state.warned_civilians:
                for ws in list(state.warned_civilians.keys()):
                    try:
                        await ws.send_json({"v": 1, "type": "ambulance.clear"})
                    except Exception:
                        pass
                state.warned_civilians.clear()
            return

        # Active dispatch: check all subscribed civilian connections
        subscriptions = await realtime_manager.get_subscriptions()

        for ws, sub in list(subscriptions.items()):
            if sub.role != "civilian" or sub.lat is None or sub.lng is None:
                continue

            dist_m = haversine_distance_m(sub.lat, sub.lng, lat, lng)
            if dist_m <= settings.AMBULANCE_WARN_RADIUS_M:
                last_warn = state.warned_civilians.get(ws, 0.0)
                if (now - last_warn) >= settings.CIVILIAN_WARN_MIN_INTERVAL_S:
                    bearing_deg = calculate_bearing_deg(lat, lng, sub.lat, sub.lng)

                    # Compute approaching trend from history
                    approaching = True
                    if len(state.history) >= 2:
                        prev_lat, prev_lng, _ = state.history[-2]
                        prev_dist = haversine_distance_m(sub.lat, sub.lng, prev_lat, prev_lng)
                        approaching = dist_m < prev_dist

                    speed_mps = (speed / 3.6) if speed > 5.0 else 11.1  # ~40 km/h emergency speed
                    eta_s = max(1.0, round(dist_m / speed_mps, 1))

                    try:
                        await ws.send_json({
                            "v": 1,
                            "type": "ambulance.nearby",
                            "distance_m": round(dist_m, 1),
                            "bearing_deg": round(bearing_deg, 1),
                            "approaching": approaching,
                            "eta_s": eta_s,
                            "expires_in_s": 10,
                        })
                        state.warned_civilians[ws] = now
                    except Exception:
                        pass
            else:
                # Was previously warned, now outside warning radius
                if ws in state.warned_civilians:
                    try:
                        await ws.send_json({"v": 1, "type": "ambulance.clear"})
                    except Exception:
                        pass
                    state.warned_civilians.pop(ws, None)

    async def sweep_stale_ambulances(self, db: AsyncSession) -> None:
        """Mark ambulances offline if no location updates received within AMBULANCE_LOCATION_STALE_S."""
        now = time.time()
        stale_ids = []

        async with self._lock:
            for amb_id, state in list(self._states.items()):
                if state.updated_at > 0 and (now - state.updated_at) > settings.AMBULANCE_LOCATION_STALE_S:
                    stale_ids.append((amb_id, state))

        for amb_id_str, state in stale_ids:
            try:
                stmt = select(Ambulance).where(Ambulance.id == amb_id_str)
                res = await db.execute(stmt)
                amb = res.scalar_one_or_none()
                if amb and amb.status != AmbulanceStatus.offline:
                    amb.status = AmbulanceStatus.offline
                    await db.commit()
                    logger.info("Ambulance %s marked offline due to stale telemetry.", amb_id_str)
                    await realtime_manager.send_to_role("admin", {
                        "v": 1,
                        "type": "ambulance.stale",
                        "ambulance_id": amb_id_str,
                    })
            except Exception as exc:
                logger.warning("Error checking stale ambulance %s: %s", amb_id_str, exc)


ambulance_tracker = AmbulanceTrackerService()
