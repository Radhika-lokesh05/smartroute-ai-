"""Unit and integration tests for Hospitals, Ambulance Live Tracking, and Dispatch services."""
import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from geoalchemy2.elements import WKTElement

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.ambulance import Ambulance, AmbulanceStatus
from app.models.dispatch import Dispatch, DispatchStatus
from app.models.hospital import Hospital
from app.models.incident import Incident, IncidentStatus, IncidentType
from app.models.user import User, UserRole
from app.services.ambulance_tracker import ambulance_tracker, AmbulanceTrackerService
from app.services.dispatch_service import dispatch_service
from app.services.hospital_service import hospital_service
from app.core.cache import cache
from app.services.realtime import realtime_manager


@pytest.fixture(autouse=True)
def reset_state():
    cache.clear()
    realtime_manager.clear()
    yield
    cache.clear()
    realtime_manager.clear()


async def create_user(
    db: AsyncSession,
    role: UserRole = UserRole.civilian,
    name: str = "Test User",
) -> tuple[User, str]:
    """Helper to create user and JWT token."""
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        name=name,
        email=f"user_{user_id.hex[:8]}@example.com",
        password_hash=get_password_hash("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(subject=str(user.id), role=role.value)
    return user, token


async def create_ambulance(
    db: AsyncSession,
    user: User,
    is_verified: bool = True,
    status: AmbulanceStatus = AmbulanceStatus.available,
    lat: float = 12.9716,
    lng: float = 77.5946,
) -> Ambulance:
    """Helper to create an ambulance record."""
    amb = Ambulance(
        id=uuid.uuid4(),
        user_id=user.id,
        plate_number=f"KA-01-{uuid.uuid4().hex[:4].upper()}",
        status=status,
        is_verified=is_verified,
        last_location=WKTElement(f"POINT({lng} {lat})", srid=4326),
    )
    db.add(amb)
    await db.commit()
    await db.refresh(amb)
    return amb


async def create_hospital(
    db: AsyncSession,
    name: str,
    lat: float,
    lng: float,
    emergency_types: list[str] | None = None,
    has_emergency: bool = True,
) -> Hospital:
    """Helper to create a test hospital."""
    hosp = Hospital(
        id=uuid.uuid4(),
        name=name,
        location=WKTElement(f"POINT({lng} {lat})", srid=4326),
        address="123 Hospital Road, Bengaluru",
        phone="+91-80-22223333",
        has_emergency=has_emergency,
        simulated_beds=50,
        beds_simulated=True,
        emergency_types=emergency_types or ["general"],
        is_24x7=True,
        source="osm",
        osm_attribution="© OpenStreetMap contributors",
    )
    db.add(hosp)
    await db.commit()
    await db.refresh(hosp)
    return hosp


async def create_incident(
    db: AsyncSession,
    lat: float = 12.9716,
    lng: float = 77.5946,
    inc_type: IncidentType = IncidentType.accident,
) -> Incident:
    """Helper to create a verified incident."""
    inc = Incident(
        id=uuid.uuid4(),
        location=WKTElement(f"POINT({lng} {lat})", srid=4326),
        incident_type=inc_type,
        status=IncidentStatus.validated,
        confirmations=3,
        rejections=0,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    db.add(inc)
    await db.commit()
    await db.refresh(inc)
    return inc


# ===========================================================================
# 1. Configuration Defaults Test
# ===========================================================================
def test_config_defaults():
    assert settings.OVERPASS_URL == "https://overpass-api.de/api/interpreter"
    assert settings.HOSPITAL_SEARCH_RADIUS_M == 15000.0
    assert settings.HOSPITAL_PREFILTER_COUNT == 6
    assert settings.HOSPITAL_ROUTE_COUNT == 3
    assert settings.AMBULANCE_LOCATION_MIN_INTERVAL_S == 2.0
    assert settings.AMBULANCE_LOCATION_STALE_S == 30.0
    assert settings.AMBULANCE_DB_FLUSH_S == 15.0
    assert settings.AMBULANCE_WARN_RADIUS_M == 1500.0
    assert settings.CIVILIAN_WARN_MIN_INTERVAL_S == 5.0
    assert settings.DISPATCH_CANDIDATE_RADIUS_M == 10000.0
    assert settings.DISPATCH_CANDIDATE_ROUTE_COUNT == 3
    assert settings.DISPATCH_OFFER_TIMEOUT_S == 60.0
    assert settings.DISPATCH_MAX_OFFERS_PER_INCIDENT == 5
    assert settings.EMERGENCY_NUMBER == "112"


# ===========================================================================
# 2. Hospital Ranking & Nearby API Tests
# ===========================================================================
@pytest.mark.asyncio
async def test_nearby_hospitals_unauthenticated(auth_client: AsyncClient):
    resp = await auth_client.get("/api/hospitals/nearby?lat=12.9716&lng=77.5946")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_nearby_hospitals_ranking_and_fields(
    auth_client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    user, token = await create_user(db_session, UserRole.civilian)
    headers = {"Authorization": f"Bearer {token}"}

    # Seed 4 hospitals at varying distances
    # Origin: (12.9716, 77.5946)
    h1 = await create_hospital(db_session, "Victoria Trauma Care", 12.9650, 77.5850, ["general", "trauma"])
    h2 = await create_hospital(db_session, "Jayadeva Cardiac Institute", 12.9180, 77.5980, ["general", "cardiac"])
    h3 = await create_hospital(db_session, "Bowring General Hospital", 12.9820, 77.6050, ["general"])
    h4 = await create_hospital(db_session, "Far Away Hospital", 13.1500, 77.6000, ["general"])  # > 15km

    # Mock routing_service.get_routes so tests do not rely on live ORS network quota
    from app.schemas.routing import GeoJSONLineString, RouteItem, RouteResponse
    async def mock_get_routes(origin, destination, *args, **kwargs):
        return RouteResponse(
            routes=[
                RouteItem(
                    rank=1,
                    distance_m=2500.0,
                    duration_s=360.0,
                    adjusted_duration_s=390.0,
                    geometry=GeoJSONLineString(coordinates=[[77.5946, 12.9716], [77.5850, 12.9650]]),
                    reason="Fastest available corridor",
                )
            ]
        )
    monkeypatch.setattr("app.services.hospital_service.routing_service.get_routes", mock_get_routes)

    resp = await auth_client.get(
        "/api/hospitals/nearby?lat=12.9716&lng=77.5946",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["emergency_number"] == "112"
    assert "Bed numbers are simulated" in data["disclaimer"]
    assert len(data["hospitals"]) >= 3

    # Check best hospital has route geometry, while rank > 1 does not
    first = data["hospitals"][0]
    assert first["beds_simulated"] is True
    assert first["simulated_beds"] >= 0
    assert first["route_geometry"] is not None

    for other in data["hospitals"][1:]:
        assert other["route_geometry"] is None
        assert other["beds_simulated"] is True


@pytest.mark.asyncio
async def test_nearby_hospitals_emergency_type_filtering(
    auth_client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    user, token = await create_user(db_session, UserRole.civilian)
    headers = {"Authorization": f"Bearer {token}"}

    await create_hospital(db_session, "General Hospital", 12.9720, 77.5950, ["general"])
    await create_hospital(db_session, "Super Burns Center", 12.9730, 77.5960, ["general", "burns"])

    from app.schemas.routing import GeoJSONLineString, RouteItem, RouteResponse
    async def mock_get_routes(origin, destination, *args, **kwargs):
        return RouteResponse(
            routes=[
                RouteItem(
                    rank=1,
                    distance_m=1000.0,
                    duration_s=120.0,
                    adjusted_duration_s=120.0,
                    geometry=GeoJSONLineString(coordinates=[[77.5946, 12.9716], [77.5950, 12.9720]]),
                    reason="Direct",
                )
            ]
        )
    monkeypatch.setattr("app.services.hospital_service.routing_service.get_routes", mock_get_routes)

    # Query for burns specialty
    resp = await auth_client.get(
        "/api/hospitals/nearby?lat=12.9716&lng=77.5946&emergency_type=burns",
        headers=headers,
    )
    assert resp.status_code == 200
    hospitals = resp.json()["hospitals"]
    assert len(hospitals) >= 1
    assert hospitals[0]["name"] == "Super Burns Center"
    assert hospitals[0]["matches_type"] is True

    # Query for specialty not available -> fallback with matches_type=False
    resp2 = await auth_client.get(
        "/api/hospitals/nearby?lat=12.9716&lng=77.5946&emergency_type=maternity",
        headers=headers,
    )
    assert resp2.status_code == 200
    hospitals2 = resp2.json()["hospitals"]
    assert len(hospitals2) >= 1
    assert hospitals2[0]["matches_type"] is False


@pytest.mark.asyncio
async def test_nearby_hospitals_routing_fallback_to_straight_line(
    auth_client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    user, token = await create_user(db_session, UserRole.civilian)
    headers = {"Authorization": f"Bearer {token}"}
    await create_hospital(db_session, "Fallback Hospital", 12.9720, 77.5950, ["general"])

    # Simulate routing failure
    async def mock_fail_routes(origin, destination, *args, **kwargs):
        raise RuntimeError("ORS Quota Exceeded")
    monkeypatch.setattr("app.services.hospital_service.routing_service.get_routes", mock_fail_routes)

    resp = await auth_client.get(
        "/api/hospitals/nearby?lat=12.9716&lng=77.5946",
        headers=headers,
    )
    assert resp.status_code == 200
    hospitals = resp.json()["hospitals"]
    assert len(hospitals) >= 1
    assert hospitals[0]["eta_estimated"] is True
    assert hospitals[0]["route_geometry"] is None


# ===========================================================================
# 3. Ambulance Status Management Tests
# ===========================================================================
@pytest.mark.asyncio
async def test_ambulance_status_permissions(
    auth_client: AsyncClient, db_session: AsyncSession
):
    # Civilian user receives 403
    civ_user, civ_token = await create_user(db_session, UserRole.civilian)
    resp = await auth_client.patch(
        "/api/ambulance/status",
        headers={"Authorization": f"Bearer {civ_token}"},
        json={"status": "available"},
    )
    assert resp.status_code == 403

    # Unverified ambulance receives 403
    amb_user, amb_token = await create_user(db_session, UserRole.ambulance)
    await create_ambulance(db_session, amb_user, is_verified=False)
    resp2 = await auth_client.patch(
        "/api/ambulance/status",
        headers={"Authorization": f"Bearer {amb_token}"},
        json={"status": "available"},
    )
    assert resp2.status_code == 403

    # Verified ambulance toggles available and offline
    amb_user2, amb_token2 = await create_user(db_session, UserRole.ambulance)
    await create_ambulance(db_session, amb_user2, is_verified=True, status=AmbulanceStatus.available)

    resp_offline = await auth_client.patch(
        "/api/ambulance/status",
        headers={"Authorization": f"Bearer {amb_token2}"},
        json={"status": "offline"},
    )
    assert resp_offline.status_code == 200
    assert resp_offline.json()["status"] == "offline"

    resp_avail = await auth_client.patch(
        "/api/ambulance/status",
        headers={"Authorization": f"Bearer {amb_token2}"},
        json={"status": "available"},
    )
    assert resp_avail.status_code == 200
    assert resp_avail.json()["status"] == "available"

    # Status 'busy' is rejected
    resp_busy = await auth_client.patch(
        "/api/ambulance/status",
        headers={"Authorization": f"Bearer {amb_token2}"},
        json={"status": "busy"},
    )
    assert resp_busy.status_code == 400
    assert "dispatch system" in resp_busy.json()["detail"].lower()


# ===========================================================================
# 4. Ambulance Live Tracking & Telemetry Tests
# ===========================================================================
@pytest.mark.asyncio
async def test_ambulance_speed_jump_and_rate_limit(db_session: AsyncSession):
    user, _ = await create_user(db_session, UserRole.ambulance)
    amb = await create_ambulance(db_session, user, is_verified=True)

    tracker = AmbulanceTrackerService()

    # Initial position
    res1 = await tracker.process_location_update(
        ambulance=amb,
        user=user,
        lat=12.9716,
        lng=77.5946,
        heading=90.0,
        speed=30.0,
        db=db_session,
    )
    assert res1 is True

    # Immediate second update (under AMBULANCE_LOCATION_MIN_INTERVAL_S = 2s) is dropped
    res_too_fast = await tracker.process_location_update(
        ambulance=amb,
        user=user,
        lat=12.9717,
        lng=77.5947,
        heading=90.0,
        speed=30.0,
        db=db_session,
    )
    assert res_too_fast is False

    # Simulate fast-forwarding timestamp with an impossible distance jump (> 150 km/h)
    state = tracker._states[str(amb.id)]
    state.updated_at = time.time() - 3.0  # 3 seconds ago
    # 3 seconds, jump from 12.9716 to 13.0716 (~11 km = ~13,200 km/h)
    res_jump = await tracker.process_location_update(
        ambulance=amb,
        user=user,
        lat=13.0716,
        lng=77.5946,
        heading=0.0,
        speed=50.0,
        db=db_session,
    )
    assert res_jump is False


@pytest.mark.asyncio
async def test_stale_ambulance_sweep(db_session: AsyncSession):
    user, _ = await create_user(db_session, UserRole.ambulance)
    amb = await create_ambulance(db_session, user, is_verified=True, status=AmbulanceStatus.available)

    tracker = AmbulanceTrackerService()
    # Process update
    await tracker.process_location_update(
        ambulance=amb,
        user=user,
        lat=12.9716,
        lng=77.5946,
        heading=0.0,
        speed=20.0,
        db=db_session,
    )

    # Artificially age the telemetry past settings.AMBULANCE_LOCATION_STALE_S (30s)
    state = tracker._states[str(amb.id)]
    state.updated_at = time.time() - 40.0

    await tracker.sweep_stale_ambulances(db_session)

    # Verify ambulance marked offline in database
    await db_session.refresh(amb)
    assert amb.status == AmbulanceStatus.offline


# ===========================================================================
# 5. Civilian Proximity Warning Tests
# ===========================================================================
@pytest.mark.asyncio
async def test_civilian_proximity_warning_active_dispatch_only(
    db_session: AsyncSession,
):
    amb_user, _ = await create_user(db_session, UserRole.ambulance)
    amb = await create_ambulance(db_session, amb_user, is_verified=True, status=AmbulanceStatus.available)
    inc = await create_incident(db_session, lat=12.9716, lng=77.5946)

    tracker = AmbulanceTrackerService()

    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send_json(self, data):
            self.messages.append(data)

    mock_ws = MockWebSocket()
    # Subscribe mock civilian at 500m away (12.9716, 77.5900)
    await realtime_manager.connect(mock_ws, user_id="civ-1", role="civilian")
    await realtime_manager.subscribe_area(mock_ws, lat=12.9716, lng=77.5900, radius_m=2000.0)

    # Case 1: Ambulance is available (no dispatch) -> NO nearby alert sent to civilian
    await tracker.process_location_update(
        ambulance=amb,
        user=amb_user,
        lat=12.9716,
        lng=77.5946,
        heading=270.0,
        speed=40.0,
        db=db_session,
    )
    assert len(mock_ws.messages) == 0

    # Case 2: Ambulance gets an active dispatch (en_route_to_scene) and status busy
    disp = Dispatch(
        id=uuid.uuid4(),
        incident_id=inc.id,
        ambulance_id=amb.id,
        status=DispatchStatus.en_route_to_scene,
        offer_number=1,
    )
    amb.status = AmbulanceStatus.busy
    db_session.add(disp)
    await db_session.commit()

    # Advance time to satisfy MIN_INTERVAL_S and stay below 150 km/h speed threshold
    state = tracker._states[str(amb.id)]
    state.updated_at = time.time() - 15.0

    # Ambulance moves closer to civilian
    await tracker.process_location_update(
        ambulance=amb,
        user=amb_user,
        lat=12.9716,
        lng=77.5920,
        heading=270.0,
        speed=40.0,
        db=db_session,
    )

    # Verify civilian received proximity warning
    assert len(mock_ws.messages) == 1
    msg = mock_ws.messages[0]
    assert msg["v"] == 1
    assert msg["type"] == "ambulance.nearby"
    assert "distance_m" in msg
    assert "bearing_deg" in msg
    assert msg["approaching"] is True
    assert msg["expires_in_s"] == 10

    # Clean up mock ws subscription
    await realtime_manager.disconnect(mock_ws)


# ===========================================================================
# 6. Dispatch Lifecycle Tests (Trigger, Accept, Decline, Progress, Sweep)
# ===========================================================================
@pytest.mark.asyncio
async def test_dispatch_lifecycle(
    auth_client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    admin_user, admin_token = await create_user(db_session, UserRole.admin)
    amb_user, amb_token = await create_user(db_session, UserRole.ambulance)
    amb = await create_ambulance(
        db_session,
        amb_user,
        is_verified=True,
        status=AmbulanceStatus.available,
        lat=12.9716,
        lng=77.5946,
    )
    inc = await create_incident(db_session, lat=12.9750, lng=77.5950)

    # Mock routing for dispatch candidate
    from app.schemas.routing import GeoJSONLineString, RouteItem, RouteResponse
    async def mock_get_routes(origin, destination, *args, **kwargs):
        return RouteResponse(
            routes=[
                RouteItem(
                    rank=1,
                    distance_m=1200.0,
                    duration_s=180.0,
                    adjusted_duration_s=200.0,
                    geometry=GeoJSONLineString(coordinates=[[77.5946, 12.9716], [77.5950, 12.9750]]),
                    reason="Clear",
                )
            ]
        )
    monkeypatch.setattr("app.services.dispatch_service.routing_service.get_routes", mock_get_routes)

    # 1. Trigger Dispatch (Admin)
    trig_resp = await auth_client.post(
        "/api/dispatches/trigger",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"incident_id": str(inc.id)},
    )
    assert trig_resp.status_code == 200
    disp_data = trig_resp.json()
    disp_id = disp_data["id"]
    assert disp_data["status"] == "offered"
    assert disp_data["ambulance_id"] == str(amb.id)
    assert disp_data["offer_number"] == 1

    # Triggering again while an offer is active returns existing open dispatch
    dup_resp = await auth_client.post(
        "/api/dispatches/trigger",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"incident_id": str(inc.id)},
    )
    assert dup_resp.status_code == 200
    assert dup_resp.json()["id"] == disp_id

    # 2. Accept Dispatch (Ambulance)
    acc_resp = await auth_client.post(
        f"/api/dispatches/{disp_id}/accept",
        headers={"Authorization": f"Bearer {amb_token}"},
    )
    assert acc_resp.status_code == 200
    acc_data = acc_resp.json()
    assert acc_data["status"] == "en_route_to_scene"
    assert acc_data["accepted_at"] is not None

    # Verify ambulance status flipped to busy
    await db_session.refresh(amb)
    assert amb.status == AmbulanceStatus.busy

    # 3. Progress Updates (at_scene -> to_hospital -> completed)
    hosp = await create_hospital(db_session, "Receiving Hospital", 12.9800, 77.6000)

    # Advance to at_scene
    prog1 = await auth_client.patch(
        f"/api/dispatches/{disp_id}/progress",
        headers={"Authorization": f"Bearer {amb_token}"},
        json={"status": "at_scene"},
    )
    assert prog1.status_code == 200
    assert prog1.json()["status"] == "at_scene"
    assert prog1.json()["arrived_at"] is not None

    # Advance to to_hospital with hospital_id
    prog2 = await auth_client.patch(
        f"/api/dispatches/{disp_id}/progress",
        headers={"Authorization": f"Bearer {amb_token}"},
        json={"status": "to_hospital", "hospital_id": str(hosp.id)},
    )
    assert prog2.status_code == 200
    assert prog2.json()["status"] == "to_hospital"
    assert prog2.json()["hospital_id"] == str(hosp.id)
    assert prog2.json()["picked_up_at"] is not None

    # Advance to completed
    prog3 = await auth_client.patch(
        f"/api/dispatches/{disp_id}/progress",
        headers={"Authorization": f"Bearer {amb_token}"},
        json={"status": "completed"},
    )
    assert prog3.status_code == 200
    assert prog3.json()["status"] == "completed"
    assert prog3.json()["completed_at"] is not None

    # Verify ambulance status flipped back to available
    await db_session.refresh(amb)
    assert amb.status == AmbulanceStatus.available


@pytest.mark.asyncio
async def test_dispatch_decline_reoffers(
    auth_client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    admin_user, admin_token = await create_user(db_session, UserRole.admin)
    amb_user1, amb_token1 = await create_user(db_session, UserRole.ambulance)
    amb_user2, amb_token2 = await create_user(db_session, UserRole.ambulance)

    # amb1 is closer to incident (12.9750, 77.5950) than amb2
    amb1 = await create_ambulance(db_session, amb_user1, is_verified=True, lat=12.9740, lng=77.5950)
    amb2 = await create_ambulance(db_session, amb_user2, is_verified=True, lat=12.9710, lng=77.5950)
    inc = await create_incident(db_session, lat=12.9750, lng=77.5950)

    from app.schemas.routing import GeoJSONLineString, RouteItem, RouteResponse
    async def mock_get_routes(origin, destination, *args, **kwargs):
        return RouteResponse(
            routes=[
                RouteItem(
                    rank=1,
                    distance_m=1000.0,
                    duration_s=100.0,
                    adjusted_duration_s=100.0,
                    geometry=GeoJSONLineString(coordinates=[[77.5946, 12.9716], [77.5950, 12.9730]]),
                    reason="Clear",
                )
            ]
        )
    monkeypatch.setattr("app.services.dispatch_service.routing_service.get_routes", mock_get_routes)

    # Trigger offer -> goes to amb1
    trig_resp = await auth_client.post(
        "/api/dispatches/trigger",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"incident_id": str(inc.id)},
    )
    assert trig_resp.status_code == 200
    disp_id = trig_resp.json()["id"]

    # amb1 declines -> automatically re-triggers and creates offer for amb2
    dec_resp = await auth_client.post(
        f"/api/dispatches/{disp_id}/decline",
        headers={"Authorization": f"Bearer {amb_token1}"},
        json={"reason": "Mechanical failure"},
    )
    assert dec_resp.status_code == 200
    assert dec_resp.json()["status"] == "declined"

    # Check that a new offer was created for amb2
    stmt = (
        select(Dispatch)
        .where(Dispatch.incident_id == inc.id, Dispatch.status == DispatchStatus.offered)
    )
    res = await db_session.execute(stmt)
    new_disp = res.scalar_one_or_none()
    assert new_disp is not None
    assert new_disp.ambulance_id == amb2.id
    assert new_disp.offer_number == 2
