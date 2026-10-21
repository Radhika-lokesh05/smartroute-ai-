"""API routers package."""
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.geocode import router as geocode_router
from app.api.routes import router as routes_router

__all__ = [
    "health_router",
    "auth_router",
    "admin_router",
    "geocode_router",
    "routes_router",
]
