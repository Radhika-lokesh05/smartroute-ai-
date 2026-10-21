import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.middleware import SecurityHeadersMiddleware, RequestBodyLimitMiddleware
from app.core.logging import configure_logging, request_id_ctx_var
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.geocode import router as geocode_router
from app.api.routes import router as routes_router
from app.api.incidents import router as incidents_router
from app.api.websocket import router as websocket_router
from app.api.weather import router as weather_router
from app.api.traffic import router as traffic_router
from app.api.hospitals import router as hospitals_router
from app.api.ambulance import router as ambulance_router
from app.api.dispatches import router as dispatches_router
from app.services.incident_service import (
    expire_old_incidents,
    extract_incident_lat_lng,
    serialize_incident_dict,
)
from app.services.realtime import create_realtime_message, realtime_manager
from app.services.ambulance_tracker import ambulance_tracker
from app.services.dispatch_service import dispatch_service

logger = logging.getLogger("smartroute.main")


async def incident_expiry_background_loop() -> None:
    """
    Background sweep running every 60 seconds to expire stale incidents.
    Cleanly shuts down on cancellation and never crashes the server if a sweep fails.
    """
    while True:
        try:
            await asyncio.sleep(60)
            async with AsyncSessionLocal() as session:
                expired = await expire_old_incidents(session)
                for inc in expired:
                    lat, lng = extract_incident_lat_lng(inc.location)
                    payload = serialize_incident_dict(inc, lat, lng)
                    await realtime_manager.broadcast_to_area(
                        lat,
                        lng,
                        create_realtime_message("incident.expired", payload),
                    )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(f"[expiry_loop] Periodic sweep error: {exc}", exc_info=True)


async def emergency_background_loop() -> None:
    """
    Background sweep running every 10 seconds to:
    1. Mark stale ambulances offline if no telemetry received within AMBULANCE_LOCATION_STALE_S.
    2. Expire unaccepted dispatch offers exceeding DISPATCH_OFFER_TIMEOUT_S and advance to next candidate.
    """
    while True:
        try:
            await asyncio.sleep(10)
            async with AsyncSessionLocal() as session:
                await ambulance_tracker.sweep_stale_ambulances(session)
                await dispatch_service.sweep_expired_offers(session)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(f"[emergency_loop] Periodic sweep error: {exc}", exc_info=True)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generates or propagates a request ID for distributed tracing and structured logging."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx_var.set(req_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_ctx_var.reset(token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan enforcing production security, logging setup, and background workers."""
    is_prod = settings.ENV.lower() == "production"
    configure_logging(is_production=is_prod)

    # 1. Enforce strict production configuration validation
    settings.validate_production_security()

    # 2. Database migrations check
    try:
        from alembic.config import Config
        from alembic import command
        from pathlib import Path
        backend_dir = Path(__file__).resolve().parent.parent
        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
        logger.info("[lifespan] Database migrations synchronized to HEAD.")
    except Exception as exc:
        logger.warning(f"[lifespan] Alembic upgrade check: {exc}")

    # 2b. Auto-seed emergency hospitals if table is empty
    try:
        from app.services.hospital_service import hospital_service
        async with AsyncSessionLocal() as session:
            await hospital_service.ensure_hospitals_seeded(session)
    except Exception as exc:
        logger.warning(f"[lifespan] Hospital seeding check: {exc}")

    # 3. Start background loops
    expiry_task = asyncio.create_task(incident_expiry_background_loop())
    emergency_task = asyncio.create_task(emergency_background_loop())
    try:
        yield
    finally:
        expiry_task.cancel()
        emergency_task.cancel()
        try:
            await asyncio.gather(expiry_task, emergency_task, return_exceptions=True)
        except asyncio.CancelledError:
            pass


# Production hardening: disable interactive documentation in production
is_production = settings.ENV.lower() == "production"

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Emergency-aware routing, incident prioritization, and hospital suggestion backend.",
    version="0.1.0",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
    lifespan=lifespan,
)

# 1. Request ID and Tracing Middleware
app.add_middleware(RequestIdMiddleware)

# 2. Security Headers & Payload Size Limits
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestBodyLimitMiddleware)

# 3. CORS Configuration (Strictly from settings)
origins = settings.ALLOWED_ORIGINS if isinstance(settings.ALLOWED_ORIGINS, list) else [settings.ALLOWED_ORIGINS]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all global exception handler.
    Returns a generic 500 error response with request_id for client correlation.
    NEVER leaks internal stack traces, database schema, or SQL strings.
    """
    req_id = request_id_ctx_var.get() or request.headers.get("X-Request-ID") or "unknown"
    logger.error(
        f"[global_exception] Unhandled error during {request.method} {request.url.path} (request_id={req_id}): {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": req_id,
        },
        headers={"X-Request-ID": req_id},
    )


# Mount Routers
app.include_router(health_router)
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(geocode_router)
app.include_router(routes_router)
app.include_router(incidents_router)
app.include_router(websocket_router)
app.include_router(weather_router)
app.include_router(traffic_router)
app.include_router(hospitals_router)
app.include_router(ambulance_router)
app.include_router(dispatches_router)


@app.get("/", tags=["Root"])
async def root() -> dict:
    """Root endpoint welcoming clients to SmartRoute AI API."""
    docs_link = None if is_production else "/docs"
    return {
        "service": settings.PROJECT_NAME,
        "status": "online",
        "docs": docs_link,
        "health": "/health",
        "ready": "/ready",
    }
