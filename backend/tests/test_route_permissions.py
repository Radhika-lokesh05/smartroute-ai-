"""
Test that guarantees every FastAPI route in SmartRoute AI has an explicit security/auth decision.
If a developer adds a new route without documenting and declaring its security classification,
this test will FAIL.
"""
from fastapi.routing import APIRoute
from app.main import app

# Explicit registry of all registered routes and their designated authorization requirement:
# Format: (HTTP_METHOD, PATH_TEMPLATE) -> AUTH_LEVEL
ROUTE_SECURITY_REGISTRY = {
    # Public endpoints
    ("GET", "/"): "PUBLIC",
    ("GET", "/health"): "PUBLIC",
    ("GET", "/ready"): "PUBLIC",
    ("GET", "/api/v1/health"): "PUBLIC",
    ("GET", "/api/v1/ready"): "PUBLIC",
    ("POST", "/api/auth/register"): "PUBLIC",
    ("POST", "/api/auth/login"): "PUBLIC",
    # Authenticated endpoints (Any active role)
    ("POST", "/api/auth/logout"): "AUTHENTICATED",
    ("GET", "/api/auth/me"): "AUTHENTICATED",
    ("GET", "/api/geocode/autocomplete"): "AUTHENTICATED",
    ("GET", "/api/geocode/search"): "AUTHENTICATED",
    ("GET", "/api/geocode/reverse"): "AUTHENTICATED",
    ("GET", "/api/routes"): "AUTHENTICATED",
    ("POST", "/api/routes"): "AUTHENTICATED",
    ("POST", "/api/incidents"): "AUTHENTICATED",
    ("POST", "/api/incidents/{incident_id}/vote"): "AUTHENTICATED",
    ("POST", "/api/incidents/{incident_id}/resolve"): "AUTHENTICATED",
    ("GET", "/api/incidents/nearby"): "AUTHENTICATED",
    ("GET", "/api/incidents/{incident_id}"): "AUTHENTICATED",
    ("GET", "/api/weather"): "AUTHENTICATED",
    ("POST", "/api/traffic/predict"): "AUTHENTICATED",
    ("GET", "/api/hospitals/nearby"): "AUTHENTICATED",
    ("GET", "/api/dispatches/{id}"): "AUTHENTICATED",
    # Role-restricted: Admin only
    ("GET", "/api/admin/audit"): "ADMIN_ONLY",
    ("GET", "/api/admin/users"): "ADMIN_ONLY",
    ("PATCH", "/api/admin/users/{id}/active"): "ADMIN_ONLY",
    ("GET", "/api/admin/ambulances"): "ADMIN_ONLY",
    ("POST", "/api/admin/ambulances"): "ADMIN_ONLY",
    ("PATCH", "/api/admin/ambulances/{id}/verify"): "ADMIN_ONLY",
    ("PATCH", "/api/admin/ambulances/{id}/unverify"): "ADMIN_ONLY",
    ("POST", "/api/admin/incidents/{id}/resolve"): "ADMIN_ONLY",
    ("POST", "/api/admin/dispatches/manual"): "ADMIN_ONLY",
    ("POST", "/api/admin/dispatches/{id}/cancel"): "ADMIN_ONLY",
    ("GET", "/api/admin/dispatches"): "ADMIN_ONLY",
    ("GET", "/api/admin/metrics/summary"): "ADMIN_ONLY",
    ("GET", "/api/admin/metrics/timeseries"): "ADMIN_ONLY",
    ("GET", "/api/admin/metrics/hotspots"): "ADMIN_ONLY",
    ("GET", "/api/admin/metrics/export.csv"): "ADMIN_ONLY",
    ("GET", "/api/admin/model-info"): "ADMIN_ONLY",
    # Role-restricted: Ambulance only / Emergency
    ("GET", "/api/ambulance/me"): "AMBULANCE_ONLY",
    ("PATCH", "/api/ambulance/status"): "AMBULANCE_ONLY",
    ("POST", "/api/dispatches/trigger"): "EMERGENCY_OR_ADMIN",
    ("POST", "/api/dispatches/{id}/accept"): "AMBULANCE_ONLY",
    ("POST", "/api/dispatches/{id}/decline"): "AMBULANCE_ONLY",
    ("PATCH", "/api/dispatches/{id}/progress"): "AMBULANCE_ONLY",
    ("GET", "/api/dispatches/active"): "AMBULANCE_OR_ADMIN",
}


def test_every_route_has_explicit_auth_decision():
    """
    Ensure every registered APIRoute in the FastAPI application has an entry in ROUTE_SECURITY_REGISTRY.
    """
    unregistered_routes = []

    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                if method in ("HEAD", "OPTIONS"):
                    continue
                key = (method, route.path)
                if key not in ROUTE_SECURITY_REGISTRY:
                    unregistered_routes.append(f"{method} {route.path}")

    assert not unregistered_routes, (
        f"The following routes have NO explicit authorization decision in ROUTE_SECURITY_REGISTRY:\n"
        + "\n".join(unregistered_routes)
        + "\nEvery new route must be reviewed and added to ROUTE_SECURITY_REGISTRY and docs/route_permissions.md."
    )
