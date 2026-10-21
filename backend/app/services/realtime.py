"""
Realtime WebSocket connection and spatial pub/sub service.

NOTE: This implementation uses an in-memory connection manager behind a small interface
(RealtimePubSubInterface) so that a distributed Redis Pub/Sub backend or message broker
can replace it later without altering any incident service or endpoint logic.
"""
import asyncio
import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set
from fastapi import WebSocket
from app.core.config import settings

logger = logging.getLogger("smartroute.realtime")


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in meters using Haversine formula."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


@dataclass
class ClientSubscription:
    websocket: WebSocket
    user_id: str
    role: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius_m: float = 5000.0


class RealtimePubSubInterface(ABC):
    """
    Abstract interface for spatial pub/sub real-time dispatching.
    Allows seamlessly swapping the In-Memory implementation with a Redis-backed pub/sub
    layer in production cluster deployments.
    """

    @abstractmethod
    async def connect(self, websocket: WebSocket, user_id: str, role: str) -> bool:
        """Register an authenticated WebSocket connection. Returns False if limit exceeded."""
        pass

    @abstractmethod
    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister a WebSocket connection and clean up resources."""
        pass

    @abstractmethod
    async def subscribe_area(self, websocket: WebSocket, lat: float, lng: float, radius_m: float) -> None:
        """Update the spatial subscription filter for a connected client."""
        pass

    @abstractmethod
    async def broadcast_to_area(self, lat: float, lng: float, message: Dict[str, Any]) -> int:
        """Broadcast a message strictly to clients whose subscription area contains (lat, lng)."""
        pass


class InMemoryConnectionManager(RealtimePubSubInterface):
    """
    In-memory spatial WebSocket connection manager.
    Enforces per-user connection limits, tracks spatial bounding bubbles, and dispatches
    asynchronously without allowing slow clients to bottleneck other connections.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # Map websocket -> ClientSubscription
        self._subscriptions: Dict[WebSocket, ClientSubscription] = {}
        # Map user_id -> Set of WebSockets for that user
        self._user_connections: Dict[str, Set[WebSocket]] = {}

    def clear(self) -> None:
        """Clear all active subscriptions and connection mappings (for test isolation)."""
        self._subscriptions.clear()
        self._user_connections.clear()

    async def connect(self, websocket: WebSocket, user_id: str, role: str) -> bool:
        async with self._lock:
            existing = self._user_connections.setdefault(user_id, set())
            if len(existing) >= settings.WS_MAX_CONNECTIONS_PER_USER:
                logger.warning(
                    f"[realtime] Connection rejected: user {user_id} reached limit of {settings.WS_MAX_CONNECTIONS_PER_USER}"
                )
                return False

            existing.add(websocket)
            self._subscriptions[websocket] = ClientSubscription(
                websocket=websocket,
                user_id=user_id,
                role=role,
            )
            logger.info(f"[realtime] Client connected: user={user_id}, total_connections={len(self._subscriptions)}")
            return True

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            sub = self._subscriptions.pop(websocket, None)
            if sub:
                user_conns = self._user_connections.get(sub.user_id)
                if user_conns:
                    user_conns.discard(websocket)
                    if not user_conns:
                        self._user_connections.pop(sub.user_id, None)
                logger.info(f"[realtime] Client disconnected: user={sub.user_id}, remaining={len(self._subscriptions)}")

    async def subscribe_area(self, websocket: WebSocket, lat: float, lng: float, radius_m: float) -> None:
        async with self._lock:
            sub = self._subscriptions.get(websocket)
            if sub:
                clamped_radius = max(100.0, min(float(radius_m), settings.MAX_SUBSCRIBE_RADIUS_M))
                sub.lat = lat
                sub.lng = lng
                sub.radius_m = clamped_radius
                logger.debug(f"[realtime] Client {sub.user_id} subscribed: ({lat}, {lng}), r={clamped_radius}m")

    async def broadcast_to_area(self, lat: float, lng: float, message: Dict[str, Any]) -> int:
        """
        Dispatches message to clients whose subscribed bubble covers (lat, lng).
        Admins automatically receive incident.*, dispatch.*, hospital.*, and ambulance.*
        city-wide without radius restrictions, verified server-side.
        """
        msg_type = str(message.get("type", ""))
        is_admin_eligible = (
            msg_type.startswith("incident.")
            or msg_type.startswith("dispatch.")
            or msg_type.startswith("hospital.")
            or msg_type.startswith("ambulance.")
        )
        recipients = []
        async with self._lock:
            for ws, sub in list(self._subscriptions.items()):
                # City-wide admin subscription (verified server-side via sub.role)
                if sub.role == "admin" and is_admin_eligible:
                    recipients.append(ws)
                    continue

                # Standard spatial bubble matching for civilians / ambulances
                if sub.lat is not None and sub.lng is not None:
                    dist = haversine_distance_m(lat, lng, sub.lat, sub.lng)
                    if dist <= sub.radius_m:
                        recipients.append(ws)

        if not recipients:
            return 0

        # Dispatch concurrently to all matching recipients with per-client timeout
        dead_sockets = []

        async def _safe_send(ws: WebSocket):
            try:
                # 2.0s send timeout ensures one slow or stalled client cannot block others
                await asyncio.wait_for(ws.send_json(message), timeout=2.0)
            except Exception as exc:
                logger.warning(f"[realtime] Error sending to websocket: {exc}")
                dead_sockets.append(ws)

        await asyncio.gather(*[_safe_send(ws) for ws in recipients], return_exceptions=True)

        # Clean up any connections that died or timed out during send
        for dead_ws in dead_sockets:
            await self.disconnect(dead_ws)

        return len(recipients) - len(dead_sockets)

    async def disconnect_user(self, user_id: str, close_code: int = 4401, reason: str = "Account deactivated") -> int:
        """Forcefully terminate and unregister all active WebSockets for a given user."""
        async with self._lock:
            sockets = list(self._user_connections.get(str(user_id), set()))
        closed = 0
        for ws in sockets:
            try:
                await ws.close(code=close_code, reason=reason)
                closed += 1
            except Exception as exc:
                logger.warning(f"[realtime] Error closing socket for user {user_id}: {exc}")
            finally:
                await self.disconnect(ws)
        return closed

    def get_connection_count(self) -> int:
        return len(self._subscriptions)

    def get_user_connection_count(self, user_id: str) -> int:
        return len(self._user_connections.get(user_id, set()))

    async def send_to_user(self, user_id: str, message: Dict[str, Any]) -> int:
        """Send message to all active WebSocket connections for a specific user."""
        async with self._lock:
            sockets = list(self._user_connections.get(str(user_id), set()))
        sent = 0
        for ws in sockets:
            try:
                await asyncio.wait_for(ws.send_json(message), timeout=2.0)
                sent += 1
            except Exception:
                await self.disconnect(ws)
        return sent

    async def send_to_role(self, role: str, message: Dict[str, Any]) -> int:
        """Send message to all connected clients with a given role (e.g. 'admin')."""
        async with self._lock:
            targets = [ws for ws, sub in self._subscriptions.items() if sub.role == role]
        sent = 0
        for ws in targets:
            try:
                await asyncio.wait_for(ws.send_json(message), timeout=2.0)
                sent += 1
            except Exception:
                await self.disconnect(ws)
        return sent

    async def get_subscriptions(self) -> Dict[WebSocket, ClientSubscription]:
        """Return shallow copy of current active subscriptions."""
        async with self._lock:
            return dict(self._subscriptions)


# Global singleton instance (backed by in-memory manager)
realtime_manager = InMemoryConnectionManager()


def create_realtime_message(
    event_type: str,
    data: Dict[str, Any],
    route_impact: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Format versioned public realtime notification envelope (v=1).
    Includes route_impact: true when an incident becomes validated, resolved, or expired.
    """
    msg: Dict[str, Any] = {
        "v": 1,
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    if route_impact is not None:
        msg["route_impact"] = route_impact
    elif event_type in ("incident.validated", "incident.resolved", "incident.expired"):
        msg["route_impact"] = True
    return msg
