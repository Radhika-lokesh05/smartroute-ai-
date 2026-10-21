import json
import uuid
from typing import Any, Dict, List
import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.cache import cache
from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole
from app.services.ors_client import ors_client


@pytest.fixture(autouse=True)
def reset_cache_and_rate_limits():
    """Clear in-memory cache and rate limiter counters before and after every test."""
    cache.clear()
    rate_limiter.clear()
    yield
    cache.clear()
    rate_limiter.clear()


@pytest.fixture
async def auth_headers(db_session: AsyncSession) -> Dict[str, str]:
    """Create a persistent active civilian user and return valid Authorization Bearer headers."""
    user = User(
        id=uuid.uuid4(),
        name="Routing Test User",
        email=f"user_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("password123"),
        role=UserRole.civilian,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(subject=str(user.id), role="civilian")
    return {"Authorization": f"Bearer {token}"}


# Sample 3-Route FeatureCollection
MOCK_3_ROUTES = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[77.5946, 12.9716], [77.6000, 12.9600], [77.6245, 12.9352]],
            },
            "properties": {
                "summary": {"distance": 5400.0, "duration": 720.0},
                "segments": [
                    {
                        "distance": 5400.0,
                        "duration": 720.0,
                        "steps": [
                            {
                                "instruction": "Head south on MG Road",
                                "distance": 1200.0,
                                "duration": 150.0,
                                "name": "MG Road",
                                "type": 11,
                            },
                            {
                                "instruction": "Turn left onto Hosur Rd",
                                "distance": 4200.0,
                                "duration": 570.0,
                                "name": "Hosur Rd",
                                "type": 1,
                            },
                        ],
                    }
                ],
            },
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[77.5946, 12.9716], [77.6100, 12.9500], [77.6245, 12.9352]],
            },
            "properties": {
                "summary": {"distance": 5800.0, "duration": 780.0},
                "segments": [{"distance": 5800.0, "duration": 780.0, "steps": []}],
            },
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[77.5946, 12.9716], [77.6300, 12.9550], [77.6245, 12.9352]],
            },
            "properties": {
                "summary": {"distance": 6200.0, "duration": 850.0},
                "segments": [{"distance": 6200.0, "duration": 850.0, "steps": []}],
            },
        },
    ],
}

# Sample Geocode FeatureCollection
MOCK_PELIAS_GEOCODE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [77.5946, 12.9716],
            },
            "properties": {
                "label": "Cubbon Park, Bengaluru, Karnataka, India",
                "name": "Cubbon Park",
                "locality": "Bengaluru",
                "region": "Karnataka",
                "country": "India",
            },
        }
    ],
}


@pytest.mark.asyncio
async def test_auth_required_for_all_endpoints(auth_client: AsyncClient) -> None:
    """Verify that routing and geocoding endpoints reject unauthenticated requests with 401."""
    # Routes GET
    r1 = await auth_client.get("/api/routes?from_lat=12.97&from_lng=77.59&to_lat=12.93&to_lng=77.62")
    assert r1.status_code == 401

    # Autocomplete
    r2 = await auth_client.get("/api/geocode/autocomplete?q=Bengaluru")
    assert r2.status_code == 401

    # Search
    r3 = await auth_client.get("/api/geocode/search?q=Bengaluru")
    assert r3.status_code == 401

    # Reverse
    r4 = await auth_client.get("/api/geocode/reverse?lat=12.97&lng=77.59")
    assert r4.status_code == 401


@pytest.mark.asyncio
async def test_input_validation(auth_client: AsyncClient, auth_headers: Dict[str, str]) -> None:
    """Verify strict query parameter validation for coordinates and search text."""
    # Out of bounds latitude (> 90.0)
    r1 = await auth_client.get(
        "/api/routes?from_lat=95.0&from_lng=77.59&to_lat=12.93&to_lng=77.62",
        headers=auth_headers,
    )
    assert r1.status_code == 422

    # Out of bounds longitude (> 180.0)
    r2 = await auth_client.get(
        "/api/routes?from_lat=12.97&from_lng=185.0&to_lat=12.93&to_lng=77.62",
        headers=auth_headers,
    )
    assert r2.status_code == 422

    # Query text too short (< 3 characters)
    r3 = await auth_client.get("/api/geocode/search?q=ab", headers=auth_headers)
    assert r3.status_code == 422

    # Query text too long (> 200 characters)
    r4 = await auth_client.get(f"/api/geocode/search?q={'a' * 201}", headers=auth_headers)
    assert r4.status_code == 422


@pytest.mark.asyncio
async def test_successful_route_with_3_alternatives(
    auth_client: AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Verify routing returns up to 3 alternative routes with GeoJSON geometries and steps."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert settings.ORS_DIRECTIONS_PATH in str(request.url)
        assert request.headers.get("Authorization") == settings.ORS_API_KEY
        return httpx.Response(200, json=MOCK_3_ROUTES)

    ors_client._transport = httpx.MockTransport(handler)
    await ors_client.close()

    try:
        response = await auth_client.get(
            "/api/routes?from_lat=12.9716&from_lng=77.5946&to_lat=12.9352&to_lng=77.6245",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "openrouteservice"
        assert len(data["routes"]) == 3

        # Check primary route
        primary = data["routes"][0]
        assert primary["distance_m"] == 5400.0
        assert primary["duration_s"] == 720.0
        assert primary["geometry"]["type"] == "LineString"
        assert len(primary["geometry"]["coordinates"]) == 3
        assert len(primary["steps"]) == 2
        assert primary["steps"][0]["instruction"] == "Head south on MG Road"
        assert primary["steps"][0]["name"] == "MG Road"
    finally:
        ors_client._transport = None
        await ors_client.close()


@pytest.mark.asyncio
async def test_single_route_fallback_when_no_alternatives(
    auth_client: AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Verify that when only 1 route is available, the service returns it cleanly without error."""
    single_route_data = {
        "type": "FeatureCollection",
        "features": [MOCK_3_ROUTES["features"][0]],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=single_route_data)

    ors_client._transport = httpx.MockTransport(handler)
    await ors_client.close()

    try:
        response = await auth_client.get(
            "/api/routes?from_lat=12.9716&from_lng=77.5946&to_lat=12.9352&to_lng=77.6245",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["routes"]) == 1
    finally:
        ors_client._transport = None
        await ors_client.close()


@pytest.mark.asyncio
async def test_no_route_returns_404(
    auth_client: AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Verify that ORS 404 (no route) maps cleanly to HTTP 404 without crashing."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "Could not find point within distance"})

    ors_client._transport = httpx.MockTransport(handler)
    await ors_client.close()

    try:
        response = await auth_client.get(
            "/api/routes?from_lat=12.9716&from_lng=77.5946&to_lat=12.9352&to_lng=77.6245",
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert "no viable route found" in response.json()["detail"].lower()
    finally:
        ors_client._transport = None
        await ors_client.close()


@pytest.mark.asyncio
async def test_provider_401_handled_without_secret_leak(
    auth_client: AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Verify that provider 401 returns 503 and never leaks the API key or raw errors."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "Unauthorized key: secret_12345"})

    ors_client._transport = httpx.MockTransport(handler)
    await ors_client.close()

    try:
        response = await auth_client.get(
            "/api/routes?from_lat=12.9716&from_lng=77.5946&to_lat=12.9352&to_lng=77.6245",
            headers=auth_headers,
        )
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert "secret" not in detail.lower()
        assert settings.ORS_API_KEY not in detail
    finally:
        ors_client._transport = None
        await ors_client.close()


@pytest.mark.asyncio
async def test_avoid_polygons_included_in_request_body(
    auth_client: AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Verify that avoid_polygons GeoJSON is passed through to ORS options.avoid_polygons."""
    captured_payloads: List[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        captured_payloads.append(body)
        return httpx.Response(200, json=MOCK_3_ROUTES)

    ors_client._transport = httpx.MockTransport(handler)
    await ors_client.close()

    multi_polygon = {
        "type": "MultiPolygon",
        "coordinates": [
            [
                [
                    [77.6000, 12.9600],
                    [77.6050, 12.9600],
                    [77.6050, 12.9650],
                    [77.6000, 12.9650],
                    [77.6000, 12.9600],
                ]
            ]
        ],
    }

    try:
        req_payload = {
            "from_lat": 12.9716,
            "from_lng": 77.5946,
            "to_lat": 12.9352,
            "to_lng": 77.6245,
            "avoid_polygons": multi_polygon,
        }
        response = await auth_client.post("/api/routes", json=req_payload, headers=auth_headers)
        assert response.status_code == 200
        assert len(captured_payloads) == 1
        sent_body = captured_payloads[0]
        assert "options" in sent_body
        assert "avoid_polygons" in sent_body["options"]
        assert sent_body["options"]["avoid_polygons"] == multi_polygon
    finally:
        ors_client._transport = None
        await ors_client.close()


@pytest.mark.asyncio
async def test_cache_hit_means_only_one_upstream_call(
    auth_client: AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Verify that repeated requests hit the in-memory cache and make only 1 upstream provider call."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=MOCK_3_ROUTES)

    ors_client._transport = httpx.MockTransport(handler)
    await ors_client.close()

    url = "/api/routes?from_lat=12.97160&from_lng=77.59460&to_lat=12.93520&to_lng=77.62450"
    try:
        # First call: hits upstream provider
        resp1 = await auth_client.get(url, headers=auth_headers)
        assert resp1.status_code == 200
        assert call_count == 1

        # Second call (same coordinates rounded to 5 decimals): served from cache
        resp2 = await auth_client.get(url, headers=auth_headers)
        assert resp2.status_code == 200
        assert call_count == 1
    finally:
        ors_client._transport = None
        await ors_client.close()


@pytest.mark.asyncio
async def test_geocode_mapping(
    auth_client: AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Verify that geocoding autocomplete, search, and reverse return the simplified clean schema."""
    def handler(request: httpx.Request) -> httpx.Response:
        # Ensure India boundary country filter is sent
        assert "boundary.country=IN" in str(request.url)
        return httpx.Response(200, json=MOCK_PELIAS_GEOCODE)

    ors_client._transport = httpx.MockTransport(handler)
    await ors_client.close()

    try:
        # 1. Search
        r1 = await auth_client.get("/api/geocode/search?q=Cubbon Park", headers=auth_headers)
        assert r1.status_code == 200
        data1 = r1.json()
        assert len(data1["results"]) == 1
        res1 = data1["results"][0]
        assert res1["label"] == "Cubbon Park, Bengaluru, Karnataka, India"
        assert res1["lat"] == 12.9716
        assert res1["lng"] == 77.5946
        assert res1["locality"] == "Bengaluru"

        # 2. Autocomplete
        r2 = await auth_client.get("/api/geocode/autocomplete?q=Cubbon", headers=auth_headers)
        assert r2.status_code == 200
        assert len(r2.json()["results"]) == 1

        # 3. Reverse
        r3 = await auth_client.get("/api/geocode/reverse?lat=12.9716&lng=77.5946", headers=auth_headers)
        assert r3.status_code == 200
        assert len(r3.json()["results"]) == 1
    finally:
        ors_client._transport = None
        await ors_client.close()


@pytest.mark.asyncio
async def test_rate_limiting(
    auth_client: AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Verify that exceeding user rate limit results in HTTP 429 Too Many Requests."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=MOCK_PELIAS_GEOCODE)

    ors_client._transport = httpx.MockTransport(handler)
    await ors_client.close()

    # Set temporary low rate limit for test
    rate_limiter.limit = 3

    try:
        for _ in range(3):
            # Vary query so it tests rate limit rather than cache hit
            res = await auth_client.get(f"/api/geocode/search?q=Test_{uuid.uuid4().hex[:6]}", headers=auth_headers)
            assert res.status_code == 200

        # 4th request must exceed rate limit
        res_blocked = await auth_client.get("/api/geocode/search?q=BlockedQuery", headers=auth_headers)
        assert res_blocked.status_code == 429
        assert "rate limit exceeded" in res_blocked.json()["detail"].lower()
    finally:
        rate_limiter.limit = settings.RATE_LIMIT_PER_MINUTE
        ors_client._transport = None
        await ors_client.close()


@pytest.mark.asyncio
async def test_osrm_fallback_when_enabled(
    auth_client: AsyncClient,
    auth_headers: Dict[str, str],
    monkeypatch,
) -> None:
    """Verify that when ORS fails and ROUTING_FALLBACK_ENABLED=True, OSRM fallback is used and labeled."""
    monkeypatch.setattr(settings, "ROUTING_FALLBACK_ENABLED", True)

    # Force ORS to fail with 500
    def ors_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "Internal ORS server error"})

    ors_client._transport = httpx.MockTransport(ors_handler)
    await ors_client.close()

    mock_osrm_response = {
        "code": "Ok",
        "routes": [
            {
                "distance": 5100.0,
                "duration": 690.0,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[77.5946, 12.9716], [77.6245, 12.9352]],
                },
                "legs": [
                    {
                        "distance": 5100.0,
                        "duration": 690.0,
                        "steps": [
                            {
                                "name": "Residency Road",
                                "distance": 1000.0,
                                "duration": 120.0,
                                "maneuver": {"type": "depart", "modifier": "right"},
                            }
                        ],
                    }
                ],
            }
        ],
    }

    # Mock the OSRM fallback request specifically on routing_service
    from app.services.routing_service import routing_service

    async def mock_osrm_api(url, params):
        return mock_osrm_response

    monkeypatch.setattr(routing_service, "_call_osrm_api", mock_osrm_api)

    try:
        response = await auth_client.get(
            "/api/routes?from_lat=12.9716&from_lng=77.5946&to_lat=12.9352&to_lng=77.6245",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "osrm-demo"
        assert len(data["routes"]) == 1
        assert data["routes"][0]["distance_m"] == 5100.0
    finally:
        ors_client._transport = None
        await ors_client.close()

