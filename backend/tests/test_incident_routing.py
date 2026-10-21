import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.elements import WKTElement

from app.core.cache import cache, make_route_cache_key
from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.core.security import create_access_token, get_password_hash
from app.models.incident import Incident, IncidentStatus, IncidentType
from app.models.user import User, UserRole
from app.schemas.routing import GeoJSONLineString, RouteItem, RouteResponse, RouteStep, RouteSummary
from app.services.incident_routing import (
    are_routes_near_duplicates,
    build_avoid_multipolygon,
    distance_from_point_to_linestring_m,
    find_incidents_on_route,
    generate_route_reason,
    hash_incidents_state,
)
from app.services.ors_client import ors_client, ORSProviderError
from app.services.routing_service import RoutingService, routing_service


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch):
    cache.clear()
    rate_limiter.clear()
    # Isolate incident routing algorithm tests from ML traffic variance and weather calls
    from app.services.traffic_model import traffic_model_service
    from app.services.weather_service import weather_service
    monkeypatch.setattr(
        traffic_model_service,
        "calculate_route_traffic",
        lambda coords, when=None, weather=None: (1.0, 1.0),
    )
    monkeypatch.setattr(
        weather_service,
        "get_current_weather",
        AsyncMock(return_value=None),
    )
    yield
    cache.clear()
    rate_limiter.clear()


@pytest.fixture
async def auth_headers(db_session: AsyncSession) -> Dict[str, str]:
    user = User(
        id=uuid.uuid4(),
        name="Routing Test User",
        email=f"route_user_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("password123"),
        role=UserRole.civilian,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(subject=str(user.id), role="civilian")
    return {"Authorization": f"Bearer {token}"}


def make_mock_feature(coords: List[List[float]], duration: float, distance: float = 5000.0) -> Dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coords,
        },
        "properties": {
            "summary": {"distance": distance, "duration": duration},
            "segments": [
                {
                    "distance": distance,
                    "duration": duration,
                    "steps": [
                        {
                            "instruction": "Continue",
                            "distance": distance,
                            "duration": duration,
                            "name": "Road",
                            "type": 1,
                        }
                    ],
                }
            ],
        },
    }


def make_mock_incident(
    incident_id: str,
    inc_type: IncidentType,
    status: IncidentStatus,
    lat: float,
    lng: float,
    expired: bool = False,
) -> Incident:
    now = datetime.now(timezone.utc)
    expires_at = now - timedelta(minutes=10) if expired else now + timedelta(minutes=30)
    inc = Incident(
        id=uuid.UUID(incident_id),
        reporter_id=uuid.uuid4(),
        incident_type=inc_type,
        status=status,
        location=WKTElement(f"POINT({lng} {lat})", srid=4326),
        created_at=now,
        expires_at=expires_at,
        confirmations=3 if status == IncidentStatus.validated else 1,
        rejections=0,
        trust_score=3.0 if status == IncidentStatus.validated else 1.0,
    )
    return inc


# ---------------------------------------------------------------------------
# 1. Incident on fastest route makes another route recommended
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_incident_on_fastest_route_reroutes():
    # Route 0: fastest raw (600s), goes through (12.9716, 77.5946) -> (12.9600, 77.6000) -> (12.9352, 77.6245)
    # Route 1: slower raw (700s), goes through (12.9716, 77.5946) -> (12.9500, 77.6200) -> (12.9352, 77.6245)
    r0_coords = [[77.5946, 12.9716], [77.6000, 12.9600], [77.6245, 12.9352]]
    r1_coords = [[77.5946, 12.9716], [77.6200, 12.9500], [77.6245, 12.9352]]

    mock_ors_response = {
        "type": "FeatureCollection",
        "features": [
            make_mock_feature(r0_coords, duration=600.0, distance=5000.0),
            make_mock_feature(r1_coords, duration=700.0, distance=5500.0),
        ],
    }

    # Incident right on Route 0
    inc_on_r0 = make_mock_incident(
        str(uuid.uuid4()),
        IncidentType.accident,
        IncidentStatus.validated,
        lat=12.9600,
        lng=77.6000,
    )

    service = RoutingService()
    service.get_raw_routes = AsyncMock(return_value=service._parse_ors_response(mock_ors_response))

    with patch("app.services.routing_service.get_active_corridor_incidents", AsyncMock(return_value=[(inc_on_r0, 12.9600, 77.6000)])):
        response = await service.get_routes(
            origin=(12.9716, 77.5946),
            destination=(12.9352, 77.6245),
            use_incidents=True,
            db=MagicMock(),
        )

    assert len(response.routes) >= 2
    recommended = response.routes[0]
    # Route 1 has no incident, so its adjusted duration is 700s
    # Route 0 has validated accident (+600s), so its adjusted duration is 600 + 600 = 1200s
    # Therefore, Route 1 is recommended (rank 1)
    assert recommended.adjusted_duration_s == 700.0
    assert response.summary.rerouted is True
    assert response.summary.recommended_route_index == 0


# ---------------------------------------------------------------------------
# 2. Incident far away changes nothing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_incident_far_away_changes_nothing():
    r0_coords = [[77.5946, 12.9716], [77.6000, 12.9600], [77.6245, 12.9352]]
    mock_ors_response = {
        "type": "FeatureCollection",
        "features": [
            make_mock_feature(r0_coords, duration=600.0, distance=5000.0),
        ],
    }

    # Incident 10km away
    distant_inc = make_mock_incident(
        str(uuid.uuid4()),
        IncidentType.accident,
        IncidentStatus.validated,
        lat=13.0500,
        lng=77.5000,
    )

    service = RoutingService()
    service.get_raw_routes = AsyncMock(return_value=service._parse_ors_response(mock_ors_response))

    with patch("app.services.routing_service.get_active_corridor_incidents", AsyncMock(return_value=[(distant_inc, 13.0500, 77.5000)])):
        response = await service.get_routes(
            origin=(12.9716, 77.5946),
            destination=(12.9352, 77.6245),
            use_incidents=True,
            db=MagicMock(),
        )

    route = response.routes[0]
    assert route.estimated_delay_s == 0.0
    assert route.adjusted_duration_s == 600.0
    assert len(route.incidents_on_route) == 0
    assert response.summary.rerouted is False


# ---------------------------------------------------------------------------
# 3. Pending incident has lower weight
# ---------------------------------------------------------------------------
def test_pending_incident_has_lower_weight():
    coords = [[77.5946, 12.9716], [77.6000, 12.9600]]
    # Accident base penalty = 600s. Validated weight = 1.0, Pending weight = 0.4
    pending_inc = make_mock_incident(str(uuid.uuid4()), IncidentType.accident, IncidentStatus.pending, 12.9600, 77.6000)
    validated_inc = make_mock_incident(str(uuid.uuid4()), IncidentType.accident, IncidentStatus.validated, 12.9600, 77.6000)

    _, pending_delay = find_incidents_on_route(coords, [(pending_inc, 12.9600, 77.6000)], buffer_m=100.0)
    _, validated_delay = find_incidents_on_route(coords, [(validated_inc, 12.9600, 77.6000)], buffer_m=100.0)

    assert pending_delay == round(settings.PENALTY_ACCIDENT_S * settings.PENDING_INCIDENT_WEIGHT, 1)
    assert validated_delay == float(settings.PENALTY_ACCIDENT_S)
    assert pending_delay < validated_delay


# ---------------------------------------------------------------------------
# 4. Resolved or expired incidents are ignored
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_resolved_or_expired_incidents_ignored(db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    # Add resolved incident and expired incident
    user = User(
        id=uuid.uuid4(),
        name="Reporter",
        email=f"reporter_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("password123"),
        role=UserRole.civilian,
    )
    db_session.add(user)
    await db_session.flush()

    res_inc = Incident(
        id=uuid.uuid4(),
        reporter_id=user.id,
        incident_type=IncidentType.accident,
        status=IncidentStatus.resolved,
        location=WKTElement("POINT(77.6000 12.9600)", srid=4326),
        created_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    exp_inc = Incident(
        id=uuid.uuid4(),
        reporter_id=user.id,
        incident_type=IncidentType.blockage,
        status=IncidentStatus.expired,
        location=WKTElement("POINT(77.6000 12.9600)", srid=4326),
        created_at=now - timedelta(hours=2),
        expires_at=now - timedelta(minutes=10),
    )
    db_session.add_all([res_inc, exp_inc])
    await db_session.commit()

    from app.services.incident_routing import get_active_corridor_incidents
    corridor_items = await get_active_corridor_incidents(
        db_session,
        origin=(12.9716, 77.5946),
        destination=(12.9352, 77.6245),
    )

    ids = [str(inc.id) for inc, _, _ in corridor_items]
    assert str(res_inc.id) not in ids
    assert str(exp_inc.id) not in ids


# ---------------------------------------------------------------------------
# 5. Avoid polygons are sent to ORS only when needed
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_avoid_polygons_sent_to_ors_only_when_needed():
    r0_coords = [[77.5946, 12.9716], [77.6000, 12.9600], [77.6245, 12.9352]]
    mock_base_response = {
        "type": "FeatureCollection",
        "features": [make_mock_feature(r0_coords, duration=600.0)],
    }

    # Case A: No validated incident on fastest route -> avoid_polygons NOT sent
    service = RoutingService()
    calls = []

    async def fake_get_raw(origin, destination, avoid_polygons=None):
        calls.append(avoid_polygons)
        return service._parse_ors_response(mock_base_response)

    service.get_raw_routes = fake_get_raw

    with patch("app.services.routing_service.get_active_corridor_incidents", AsyncMock(return_value=[])):
        await service.get_routes(origin=(12.9716, 77.5946), destination=(12.9352, 77.6245), db=MagicMock())

    assert len(calls) == 1
    assert calls[0] is None  # Never requested avoid_polygons

    # Case B: Validated incident on fastest route -> avoid_polygons SENT
    calls.clear()
    val_inc = make_mock_incident(str(uuid.uuid4()), IncidentType.accident, IncidentStatus.validated, 12.9600, 77.6000)

    with patch("app.services.routing_service.get_active_corridor_incidents", AsyncMock(return_value=[(val_inc, 12.9600, 77.6000)])):
        await service.get_routes(origin=(12.9716, 77.5946), destination=(12.9352, 77.6245), db=MagicMock())

    assert len(calls) == 2
    assert calls[0] is None
    assert calls[1] is not None
    assert calls[1]["type"] == "MultiPolygon"


# ---------------------------------------------------------------------------
# 6. ORS failure on avoid candidate still returns normal routes
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ors_failure_on_avoid_candidate_returns_normal_routes():
    r0_coords = [[77.5946, 12.9716], [77.6000, 12.9600], [77.6245, 12.9352]]
    mock_base_response = {
        "type": "FeatureCollection",
        "features": [make_mock_feature(r0_coords, duration=600.0)],
    }

    service = RoutingService()

    async def fake_get_raw(origin, destination, avoid_polygons=None):
        if avoid_polygons:
            raise ORSProviderError("Avoid polygon calculation failed upstream")
        return service._parse_ors_response(mock_base_response)

    service.get_raw_routes = fake_get_raw
    val_inc = make_mock_incident(str(uuid.uuid4()), IncidentType.accident, IncidentStatus.validated, 12.9600, 77.6000)

    with patch("app.services.routing_service.get_active_corridor_incidents", AsyncMock(return_value=[(val_inc, 12.9600, 77.6000)])):
        response = await service.get_routes(
            origin=(12.9716, 77.5946),
            destination=(12.9352, 77.6245),
            db=MagicMock(),
        )

    # Must not raise error; returns normal route candidate
    assert len(response.routes) == 1
    assert response.routes[0].duration_s == 600.0


# ---------------------------------------------------------------------------
# 7. Origin inside a polygon is handled
# ---------------------------------------------------------------------------
def test_origin_inside_polygon_dropped_safely():
    origin = (12.9716, 77.5946)
    dest = (12.9352, 77.6245)

    from app.schemas.routing import IncidentOnRoute

    # Incident right at origin (dist = 0m < 150m radius)
    inc_at_origin = IncidentOnRoute(
        id=str(uuid.uuid4()),
        type="accident",
        status="validated",
        lat=12.9716,
        lng=77.5946,
        distance_from_route_m=0.0,
    )

    # Valid incident away from origin and destination
    inc_mid = IncidentOnRoute(
        id=str(uuid.uuid4()),
        type="accident",
        status="validated",
        lat=12.9600,
        lng=77.6000,
        distance_from_route_m=10.0,
    )

    result = build_avoid_multipolygon(
        validated_incidents_on_fastest=[inc_at_origin, inc_mid],
        origin=origin,
        destination=dest,
        radius_m=150.0,
        max_count=10,
    )

    assert result is not None
    # Only inc_mid was kept (inc_at_origin was dropped)
    assert len(result["coordinates"]) == 1


# ---------------------------------------------------------------------------
# 8. Near-duplicate routes are merged
# ---------------------------------------------------------------------------
def test_near_duplicate_routes_merged():
    coords = [[77.5946, 12.9716], [77.6245, 12.9352]]
    r1 = RouteItem(
        distance_m=5000.0,
        duration_s=600.0,
        geometry=GeoJSONLineString(coordinates=coords),
    )
    r2 = RouteItem(
        distance_m=5005.0,  # 0.1% diff (< 1%)
        duration_s=602.0,   # 0.3% diff (< 1%)
        geometry=GeoJSONLineString(coordinates=coords),
    )
    r3 = RouteItem(
        distance_m=6000.0,  # 20% diff
        duration_s=800.0,
        geometry=GeoJSONLineString(coordinates=[[77.5946, 12.9716], [77.61, 12.95], [77.6245, 12.9352]]),
    )

    assert are_routes_near_duplicates(r1, r2) is True
    assert are_routes_near_duplicates(r1, r3) is False


# ---------------------------------------------------------------------------
# 9. Ranking uses adjusted duration
# ---------------------------------------------------------------------------
def test_ranking_uses_adjusted_duration():
    # Route A: duration 600s, delay 500s -> adjusted 1100s
    # Route B: duration 750s, delay 0s   -> adjusted 750s
    # Route C: duration 800s, delay 100s -> adjusted 900s
    coords = [[77.59, 12.97], [77.62, 12.93]]
    cand_a = RouteItem(distance_m=5000, duration_s=600, estimated_delay_s=500, adjusted_duration_s=1100, geometry=GeoJSONLineString(coordinates=coords))
    cand_b = RouteItem(distance_m=5500, duration_s=750, estimated_delay_s=0, adjusted_duration_s=750, geometry=GeoJSONLineString(coordinates=coords))
    cand_c = RouteItem(distance_m=6000, duration_s=800, estimated_delay_s=100, adjusted_duration_s=900, geometry=GeoJSONLineString(coordinates=coords))

    ranked = sorted([cand_a, cand_b, cand_c], key=lambda r: r.adjusted_duration_s)
    assert ranked[0].adjusted_duration_s == 750.0  # cand_b
    assert ranked[1].adjusted_duration_s == 900.0  # cand_c
    assert ranked[2].adjusted_duration_s == 1100.0 # cand_a


# ---------------------------------------------------------------------------
# 10. Cache invalidates when incident status changes
# ---------------------------------------------------------------------------
def test_cache_invalidates_when_incident_status_changes():
    inc_id = str(uuid.uuid4())
    inc_pending = make_mock_incident(inc_id, IncidentType.accident, IncidentStatus.pending, 12.96, 77.60)
    inc_validated = make_mock_incident(inc_id, IncidentType.accident, IncidentStatus.validated, 12.96, 77.60)

    hash_pending = hash_incidents_state([(inc_pending, 12.96, 77.60)])
    hash_validated = hash_incidents_state([(inc_validated, 12.96, 77.60)])

    assert hash_pending != hash_validated

    key1 = make_route_cache_key(12.97, 77.59, 12.93, 77.62, incidents_hash=hash_pending)
    key2 = make_route_cache_key(12.97, 77.59, 12.93, 77.62, incidents_hash=hash_validated)

    assert key1 != key2


# ---------------------------------------------------------------------------
# 11. use_incidents=false returns raw behaviour
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_use_incidents_false_returns_raw_behaviour():
    r0_coords = [[77.5946, 12.9716], [77.6000, 12.9600], [77.6245, 12.9352]]
    mock_base_response = {
        "type": "FeatureCollection",
        "features": [make_mock_feature(r0_coords, duration=600.0)],
    }

    service = RoutingService()
    service.get_raw_routes = AsyncMock(return_value=service._parse_ors_response(mock_base_response))

    val_inc = make_mock_incident(str(uuid.uuid4()), IncidentType.accident, IncidentStatus.validated, 12.9600, 77.6000)

    with patch("app.services.routing_service.get_active_corridor_incidents", AsyncMock(return_value=[(val_inc, 12.9600, 77.6000)])):
        response = await service.get_routes(
            origin=(12.9716, 77.5946),
            destination=(12.9352, 77.6245),
            use_incidents=False,
            db=MagicMock(),
        )

    route = response.routes[0]
    assert route.estimated_delay_s == 0.0
    assert route.adjusted_duration_s == 600.0
    assert len(route.incidents_on_route) == 0
    assert "disabled" in route.reason.lower()


# ---------------------------------------------------------------------------
# 12. An incident counts once per route
# ---------------------------------------------------------------------------
def test_incident_counts_once_per_route():
    # Route with multiple segments all near (12.9600, 77.6000)
    snaking_coords = [
        [77.6000, 12.9599],
        [77.6001, 12.9600],
        [77.6000, 12.9601],
        [77.5999, 12.9600],
    ]
    inc = make_mock_incident(str(uuid.uuid4()), IncidentType.blockage, IncidentStatus.validated, 12.9600, 77.6000)

    # Pass the same incident multiple times in corridor
    incidents_on_route, delay_s = find_incidents_on_route(
        snaking_coords,
        [(inc, 12.9600, 77.6000), (inc, 12.9600, 77.6000)],
        buffer_m=100.0,
    )

    assert len(incidents_on_route) == 1
    assert delay_s == float(settings.PENALTY_BLOCKAGE_S)


def test_generate_route_reason_variations():
    coords = [[77.6, 12.96], [77.62, 12.93]]
    # Normal route with no incidents
    r_clean = RouteItem(distance_m=5000, duration_s=600, geometry=GeoJSONLineString(coordinates=coords))
    assert generate_route_reason(r_clean, rank=1, raw_fastest_adjusted_duration=600) == "No incidents on this route"

    # Route with delay
    from app.schemas.routing import IncidentOnRoute
    inc = IncidentOnRoute(id="1", type="accident", status="validated", lat=12.96, lng=77.6, distance_from_route_m=10)
    r_delayed = RouteItem(
        distance_m=5000,
        duration_s=600,
        estimated_delay_s=600,
        adjusted_duration_s=1200,
        incidents_on_route=[inc],
        geometry=GeoJSONLineString(coordinates=coords),
    )
    reason = generate_route_reason(r_delayed, rank=2, raw_fastest_adjusted_duration=600)
    assert "+10 min estimated delay" in reason

    # Route avoiding incidents
    r_avoid = RouteItem(
        distance_m=5500,
        duration_s=700,
        adjusted_duration_s=700,
        avoids_incidents=True,
        geometry=GeoJSONLineString(coordinates=coords),
    )
    reason_avoid = generate_route_reason(r_avoid, rank=1, raw_fastest_adjusted_duration=1200, avoided_count=2)
    assert "Avoids 2 reported incident(s)" in reason_avoid
    assert "faster than the fastest raw route" in reason_avoid

