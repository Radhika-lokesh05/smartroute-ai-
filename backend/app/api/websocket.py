import asyncio
import json
import logging
import time
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy import select
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import decode_access_token, is_token_revoked
from app.models.user import User
from app.services.ambulance_tracker import ambulance_tracker
from app.services.realtime import realtime_manager

logger = logging.getLogger("smartroute.websocket")

router = APIRouter(tags=["WebSocket"])

MAX_WS_MESSAGE_BYTES = 16384  # 16 KB
WS_RATE_LIMIT_MESSAGES = 30
WS_RATE_LIMIT_WINDOW_S = 5.0
WS_IDLE_TIMEOUT_S = 60.0


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Hardened Realtime WebSocket Endpoint:
    - Verifies Origin header against ALLOWED_ORIGINS in production.
    - Requires {"type": "auth", "token": "..."} as first message within WS_AUTH_TIMEOUT_S.
    - Checks token revocation and user active state.
    - Enforces max message size (16 KB) and per-connection message rate limits (code 4429).
    - Enforces idle timeout (60s).
    - Catches and sanitizes invalid JSON and unknown message types without crashing.
    """
    # Step 0: Origin header check
    origin = websocket.headers.get("origin")
    origins = settings.ALLOWED_ORIGINS if isinstance(settings.ALLOWED_ORIGINS, list) else [settings.ALLOWED_ORIGINS]
    if settings.ENV.lower() == "production" and origins and "*" not in origins:
        if origin and origin not in origins:
            logger.warning(f"[ws] Rejected connection from forbidden origin: {origin}")
            await websocket.close(code=4403, reason="Forbidden origin")
            return

    await websocket.accept()

    # Step 1: Enforce authentication without token in URL
    try:
        raw_auth = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=settings.WS_AUTH_TIMEOUT_S,
        )
        if len(raw_auth.encode("utf-8")) > MAX_WS_MESSAGE_BYTES:
            await websocket.close(code=4400, reason="Auth payload too large")
            return
        auth_msg = json.loads(raw_auth)
    except asyncio.TimeoutError:
        logger.warning("[ws] Auth timeout exceeded; closing with 4401")
        await websocket.close(code=4401, reason="Authentication timeout")
        return
    except Exception as exc:
        logger.warning(f"[ws] Invalid initial message: {exc}; closing with 4401")
        await websocket.close(code=4401, reason="Initial message must be valid auth JSON")
        return

    if not isinstance(auth_msg, dict) or auth_msg.get("type") != "auth" or not auth_msg.get("token"):
        logger.warning("[ws] Missing auth type or token; closing with 4401")
        await websocket.close(code=4401, reason="First message must be auth with token")
        return

    token = str(auth_msg.get("token"))
    try:
        payload = decode_access_token(token)
        user_id = str(payload.get("sub"))
        role = str(payload.get("role", "civilian"))
        jti = payload.get("jti")
        if not user_id:
            raise ValueError("Token missing sub claim")
        if is_token_revoked(jti):
            logger.warning(f"[ws] Revoked token presented: {jti}; closing with 4401")
            await websocket.close(code=4401, reason="Token has been revoked")
            return

        # Verify user is active in database
        import uuid
        user_uuid = uuid.UUID(user_id)
        async with AsyncSessionLocal() as session:
            stmt = select(User.is_active).where(User.id == user_uuid)
            is_active = (await session.execute(stmt)).scalar_one_or_none()
            if is_active is False:
                logger.warning(f"[ws] Inactive user {user_id}; closing with 4401")
                await websocket.close(code=4401, reason="Account is deactivated")
                return
            if is_active is None and settings.ENV.lower() == "production":
                logger.warning(f"[ws] User {user_id} not found in production; closing with 4401")
                await websocket.close(code=4401, reason="User not found")
                return

    except (JWTError, ValueError) as exc:
        logger.warning(f"[ws] Token validation failed: {exc}; closing with 4401")
        await websocket.close(code=4401, reason="Invalid or expired token")
        return

    # Step 2: Enforce per-user connection limits
    connected = await realtime_manager.connect(websocket, user_id=user_id, role=role)
    if not connected:
        logger.warning(f"[ws] User {user_id} exceeded connection limit; closing with 4429")
        await websocket.close(code=4429, reason="Maximum connections per user reached")
        return

    # Confirm successful authentication
    await websocket.send_json({
        "v": 1,
        "type": "auth.success",
        "user_id": user_id,
    })

    # Message rate limiting tracker
    recent_messages: List[float] = []

    # Step 3: Event loop with rate limit, size limit, and idle timeout
    try:
        while True:
            try:
                raw_text = await asyncio.wait_for(websocket.receive_text(), timeout=WS_IDLE_TIMEOUT_S)
            except asyncio.TimeoutError:
                logger.info(f"[ws] Connection idle for {WS_IDLE_TIMEOUT_S}s for user {user_id}; closing")
                await websocket.close(code=1000, reason="Idle timeout")
                break

            # 3a. Message size limit check
            if len(raw_text.encode("utf-8")) > MAX_WS_MESSAGE_BYTES:
                await websocket.send_json({
                    "v": 1,
                    "type": "error",
                    "message": f"Message exceeds maximum size of {MAX_WS_MESSAGE_BYTES} bytes",
                })
                continue

            # 3b. Rate limit check (max 30 messages in 5 seconds)
            now = time.time()
            recent_messages = [t for t in recent_messages if now - t < WS_RATE_LIMIT_WINDOW_S]
            if len(recent_messages) >= WS_RATE_LIMIT_MESSAGES:
                logger.warning(f"[ws] Connection rate limit exceeded for user {user_id}; closing with 4429")
                await websocket.close(code=4429, reason="Message rate limit exceeded")
                break
            recent_messages.append(now)

            # 3c. Safe JSON parsing
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "v": 1,
                    "type": "error",
                    "message": "Malformed JSON payload",
                })
                continue

            if not isinstance(data, dict):
                await websocket.send_json({
                    "v": 1,
                    "type": "error",
                    "message": "Payload must be a JSON object",
                })
                continue

            msg_type = data.get("type")
            if msg_type == "subscribe":
                try:
                    lat = float(data.get("lat"))
                    lng = float(data.get("lng"))
                    radius_m = float(data.get("radius_m", 5000.0))
                    clamped_radius = max(100.0, min(radius_m, settings.MAX_SUBSCRIBE_RADIUS_M))
                    await realtime_manager.subscribe_area(websocket, lat, lng, clamped_radius)
                    await websocket.send_json({
                        "v": 1,
                        "type": "subscribe.success",
                        "lat": lat,
                        "lng": lng,
                        "radius_m": clamped_radius,
                    })
                except (TypeError, ValueError):
                    await websocket.send_json({
                        "v": 1,
                        "type": "error",
                        "message": "Invalid coordinates or radius for subscription",
                    })

            elif msg_type == "ambulance.location":
                if role != "ambulance":
                    await websocket.send_json({
                        "v": 1,
                        "type": "error",
                        "message": "Only verified ambulance users may send location updates",
                    })
                    continue

                try:
                    lat = float(data.get("lat"))
                    lng = float(data.get("lng"))
                    heading = float(data.get("heading", 0.0))
                    speed = float(data.get("speed", 0.0))
                    async with AsyncSessionLocal() as db:
                        accepted = await ambulance_tracker.update_location(
                            user_id=user_id,
                            lat=lat,
                            lng=lng,
                            heading=heading,
                            speed=speed,
                            db=db,
                        )
                    if accepted:
                        await websocket.send_json({
                            "v": 1,
                            "type": "ambulance.location.ack",
                        })
                except (TypeError, ValueError):
                    await websocket.send_json({
                        "v": 1,
                        "type": "error",
                        "message": "Invalid telemetry values for ambulance location",
                    })

            elif msg_type == "ping":
                await websocket.send_json({"v": 1, "type": "pong"})

            else:
                await websocket.send_json({
                    "v": 1,
                    "type": "error",
                    "message": f"Unknown message type '{msg_type}'",
                })

    except WebSocketDisconnect:
        logger.info(f"[ws] WebSocketDisconnect for user {user_id}")
    except Exception as exc:
        logger.warning(f"[ws] Unexpected error in socket loop: {exc}")
    finally:
        await realtime_manager.disconnect(websocket)
