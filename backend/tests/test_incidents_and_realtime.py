import asyncio
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from geoalchemy2.elements import WKTElement

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.ambulance import Ambulance, AmbulanceStatus
from app.models.incident import Incident, IncidentStatus, IncidentType, VoteType
from app.models.user import User, UserRole
from app.services.incident_service import expire_old_incidents
from app.services.realtime import create_realtime_message, realtime_manager


@pytest.fixture(autouse=True)
def cleanup_realtime():
    realtime_manager.clear()
    yield
    realtime_manager.clear()


async def create_test_user(
    db: AsyncSession,
    role: UserRole = UserRole.civilian,
    name: str = "Test User",
) -> tuple[User, str]:
    """Helper to create a user in DB and return (User, JWT token)."""
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
    token = create_access_token(subject=str(user.id), role=role.value)
    return user, token


async def create_test_ambulance(db: AsyncSession, user: User, is_verified: bool = True) -> Ambulance:
    """Helper to create an ambulance record for an ambulance user."""
    amb = Ambulance(
        id=uuid.uuid4(),
        user_id=user.id,
        plate_number=f"KA-01-{uuid.uuid4().hex[:4].upper()}",
        status=AmbulanceStatus.available,
        is_verified=is_verified,
    )
    db.add(amb)
    await db.commit()
    return amb


# ---------------------------------------------------------------------------
# 1. Create Incident
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_incident(auth_client: AsyncClient, db_session: AsyncSession) -> None:
    user, token = await create_test_user(db_session, UserRole.civilian)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "lat": 12.9716,
        "lng": 77.5946,
        "type": "accident",
        "note": "Multi-car collision on MG Road",
    }
    response = await auth_client.post("/api/incidents", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["incident_type"] == "accident"
    assert data["status"] == "pending"
    assert data["confirmations"] == 1  # Reporter's own report is first confirmation
    assert data["rejections"] == 0
    assert data["trust_score"] == 1.0
    assert data["note"] == "Multi-car collision on MG Road"
    assert data["user_voted"] is True
    assert "email" not in str(data)  # Privacy: never exposes reporter email


# ---------------------------------------------------------------------------
# 2. Duplicate Report within 100m Becomes a Vote
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_duplicate_report_within_100m_becomes_vote(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    user1, token1 = await create_test_user(db_session, UserRole.civilian, "Reporter 1")
    user2, token2 = await create_test_user(db_session, UserRole.civilian, "Reporter 2")

    # User 1 creates incident at (12.9716, 77.5946)
    resp1 = await auth_client.post(
        "/api/incidents",
        json={"lat": 12.9716, "lng": 77.5946, "type": "blockage"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp1.status_code == 201
    inc1_id = resp1.json()["id"]

    # User 2 reports same type ~25m away (12.9718, 77.5947)
    resp2 = await auth_client.post(
        "/api/incidents",
        json={"lat": 12.9718, "lng": 77.5947, "type": "blockage"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp2.status_code == 201
    data2 = resp2.json()
    # Must NOT create a new incident; must return existing incident with incremented confirmations
    assert data2["id"] == inc1_id
    assert data2["confirmations"] == 2
    assert data2["trust_score"] == 2.0

    # User 1 trying to report again returns 409
    resp_dup = await auth_client.post(
        "/api/incidents",
        json={"lat": 12.9717, "lng": 77.5946, "type": "blockage"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp_dup.status_code == 409


# ---------------------------------------------------------------------------
# 3. Vote Twice Gives 409
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_vote_twice_gives_409(auth_client: AsyncClient, db_session: AsyncSession) -> None:
    reporter, r_token = await create_test_user(db_session, name="Reporter")
    voter, v_token = await create_test_user(db_session, name="Voter")

    create_resp = await auth_client.post(
        "/api/incidents",
        json={"lat": 12.9716, "lng": 77.5946, "type": "hazard"},
        headers={"Authorization": f"Bearer {r_token}"},
    )
    inc_id = create_resp.json()["id"]

    vote_payload = {"vote": "confirm", "voter_lat": 12.9720, "voter_lng": 77.5946}
    # First vote: 200 OK
    v1 = await auth_client.post(
        f"/api/incidents/{inc_id}/vote",
        json=vote_payload,
        headers={"Authorization": f"Bearer {v_token}"},
    )
    assert v1.status_code == 200

    # Second vote: 409 Conflict
    v2 = await auth_client.post(
        f"/api/incidents/{inc_id}/vote",
        json=vote_payload,
        headers={"Authorization": f"Bearer {v_token}"},
    )
    assert v2.status_code == 409


# ---------------------------------------------------------------------------
# 4. Vote Farther than 1km is Rejected
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_vote_farther_than_1km_rejected(auth_client: AsyncClient, db_session: AsyncSession) -> None:
    reporter, r_token = await create_test_user(db_session)
    voter, v_token = await create_test_user(db_session)

    create_resp = await auth_client.post(
        "/api/incidents",
        json={"lat": 12.9716, "lng": 77.5946, "type": "accident"},
        headers={"Authorization": f"Bearer {r_token}"},
    )
    inc_id = create_resp.json()["id"]

    # Voter is ~2.5km away (12.9950, 77.5946)
    vote_resp = await auth_client.post(
        f"/api/incidents/{inc_id}/vote",
        json={"vote": "confirm", "voter_lat": 12.9950, "voter_lng": 77.5946},
        headers={"Authorization": f"Bearer {v_token}"},
    )
    assert vote_resp.status_code == 400
    assert "radius" in vote_resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5. Three Distinct Confirmations Validate Incident
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_three_confirmations_validate_incident(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    u1, t1 = await create_test_user(db_session, name="User 1")
    u2, t2 = await create_test_user(db_session, name="User 2")
    u3, t3 = await create_test_user(db_session, name="User 3")

    # 1st confirmation (creator)
    create_resp = await auth_client.post(
        "/api/incidents",
        json={"lat": 12.9716, "lng": 77.5946, "type": "accident"},
        headers={"Authorization": f"Bearer {t1}"},
    )
    inc_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "pending"
    assert create_resp.json()["confirmations"] == 1

    # 2nd confirmation
    v2 = await auth_client.post(
        f"/api/incidents/{inc_id}/vote",
        json={"vote": "confirm", "voter_lat": 12.9717, "voter_lng": 77.5946},
        headers={"Authorization": f"Bearer {t2}"},
    )
    assert v2.status_code == 200
    assert v2.json()["status"] == "pending"
    assert v2.json()["confirmations"] == 2

    # 3rd confirmation (reaches VALIDATION_THRESHOLD=3)
    v3 = await auth_client.post(
        f"/api/incidents/{inc_id}/vote",
        json={"vote": "confirm", "voter_lat": 12.9718, "voter_lng": 77.5946},
        headers={"Authorization": f"Bearer {t3}"},
    )
    assert v3.status_code == 200
    assert v3.json()["status"] == "validated"
    assert v3.json()["validated_at"] is not None


# ---------------------------------------------------------------------------
# 6. Ambulance Confirm Weight
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ambulance_confirm_weight(auth_client: AsyncClient, db_session: AsyncSession) -> None:
    reporter, r_token = await create_test_user(db_session, name="Reporter")
    amb_user, amb_token = await create_test_user(db_session, UserRole.ambulance, name="Medic")
    await create_test_ambulance(db_session, amb_user, is_verified=True)

    create_resp = await auth_client.post(
        "/api/incidents",
        json={"lat": 12.9716, "lng": 77.5946, "type": "hazard"},
        headers={"Authorization": f"Bearer {r_token}"},
    )
    inc_id = create_resp.json()["id"]
    assert create_resp.json()["trust_score"] == 1.0

    # Verified ambulance vote adds AMBULANCE_CONFIRM_WEIGHT (2.0)
    vote_resp = await auth_client.post(
        f"/api/incidents/{inc_id}/vote",
        json={"vote": "confirm", "voter_lat": 12.9717, "voter_lng": 77.5946},
        headers={"Authorization": f"Bearer {amb_token}"},
    )
    assert vote_resp.status_code == 200
    data = vote_resp.json()
    assert data["trust_score"] == 3.0  # 1.0 + 2.0 = 3.0 (reaches threshold and validates)
    assert data["status"] == "validated"


# ---------------------------------------------------------------------------
# 7. Rejections Expire Incident
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rejections_expire_incident(auth_client: AsyncClient, db_session: AsyncSession) -> None:
    reporter, r_token = await create_test_user(db_session, name="Reporter")
    v1, t1 = await create_test_user(db_session)
    v2, t2 = await create_test_user(db_session)
    v3, t3 = await create_test_user(db_session)

    create_resp = await auth_client.post(
        "/api/incidents",
        json={"lat": 12.9716, "lng": 77.5946, "type": "blockage"},
        headers={"Authorization": f"Bearer {r_token}"},
    )
    inc_id = create_resp.json()["id"]

    for token in (t1, t2):
        r = await auth_client.post(
            f"/api/incidents/{inc_id}/vote",
            json={"vote": "reject", "voter_lat": 12.9717, "voter_lng": 77.5946},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

    # 3rd rejection (rejections=3, exceeds confirmations=1)
    r3 = await auth_client.post(
        f"/api/incidents/{inc_id}/vote",
        json={"vote": "reject", "voter_lat": 12.9717, "voter_lng": 77.5946},
        headers={"Authorization": f"Bearer {t3}"},
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "expired"


# ---------------------------------------------------------------------------
# 8. Expiry Task
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_expiry_task(db_session: AsyncSession) -> None:
    user, _ = await create_test_user(db_session)
    past_time = datetime.now(timezone.utc) - timedelta(minutes=50)

    # Insert incident already past expires_at
    expired_inc = Incident(
        reporter_id=user.id,
        location=WKTElement("POINT(77.5946 12.9716)", srid=4326),
        incident_type=IncidentType.accident,
        status=IncidentStatus.pending,
        confirmations=1,
        rejections=0,
        trust_score=1.0,
        created_at=past_time - timedelta(minutes=45),
        expires_at=past_time,
    )
    db_session.add(expired_inc)
    await db_session.commit()

    expired_list = await expire_old_incidents(db_session)
    assert len(expired_list) >= 1
    target = next((i for i in expired_list if i.id == expired_inc.id), None)
    assert target is not None
    assert target.status == IncidentStatus.expired
    assert target.expiry_reason == "timeout"


# ---------------------------------------------------------------------------
# 9. Resolve Permissions
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_resolve_permissions(auth_client: AsyncClient, db_session: AsyncSession) -> None:
    reporter, r_token = await create_test_user(db_session, name="Reporter")
    civilian, c_token = await create_test_user(db_session, name="Random Civilian")
    admin, a_token = await create_test_user(db_session, UserRole.admin, name="Admin")
    amb_user, amb_token = await create_test_user(db_session, UserRole.ambulance, name="Medic")
    await create_test_ambulance(db_session, amb_user, is_verified=True)

    create_resp = await auth_client.post(
        "/api/incidents",
        json={"lat": 12.9716, "lng": 77.5946, "type": "hazard"},
        headers={"Authorization": f"Bearer {r_token}"},
    )
    inc_id = create_resp.json()["id"]

    # Random civilian cannot resolve (403)
    c_resp = await auth_client.post(
        f"/api/incidents/{inc_id}/resolve",
        headers={"Authorization": f"Bearer {c_token}"},
    )
    assert c_resp.status_code == 403

    # Reporter can resolve
    r_resp = await auth_client.post(
        f"/api/incidents/{inc_id}/resolve",
        headers={"Authorization": f"Bearer {r_token}"},
    )
    assert r_resp.status_code == 200
    assert r_resp.json()["status"] == "resolved"


# ---------------------------------------------------------------------------
# 10. Rate Limits (Reports & Votes)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rate_limits(auth_client: AsyncClient, db_session: AsyncSession) -> None:
    user, token = await create_test_user(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # 3 reports within 10 min succeed (distinct locations so they don't dedupe)
    for i in range(settings.MAX_REPORTS_PER_10_MIN):
        r = await auth_client.post(
            "/api/incidents",
            json={"lat": 12.9716 + (i * 0.05), "lng": 77.5946, "type": "accident"},
            headers=headers,
        )
        assert r.status_code == 201

    # 4th report returns 429 Too Many Requests
    r_exceeded = await auth_client.post(
        "/api/incidents",
        json={"lat": 13.1000, "lng": 77.6000, "type": "accident"},
        headers=headers,
    )
    assert r_exceeded.status_code == 429
    assert "Retry-After" in r_exceeded.headers

    # Vote rate limit (MAX_VOTES_PER_HOUR = 30)
    voter, v_token = await create_test_user(db_session, name="Vote Rate Limit User")
    target_inc = Incident(
        reporter_id=user.id,
        location=WKTElement("POINT(77.5946 12.9716)", srid=4326),
        incident_type=IncidentType.hazard,
        status=IncidentStatus.pending,
        confirmations=1,
        rejections=0,
        trust_score=1.0,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=45),
    )
    db_session.add(target_inc)
    await db_session.commit()

    from app.models.incident import IncidentVote
    now = datetime.now(timezone.utc)
    for _ in range(settings.MAX_VOTES_PER_HOUR):
        dummy_inc = Incident(
            reporter_id=user.id,
            location=WKTElement("POINT(77.5946 12.9716)", srid=4326),
            incident_type=IncidentType.accident,
            status=IncidentStatus.pending,
            confirmations=1,
            rejections=0,
            trust_score=1.0,
            created_at=now,
            expires_at=now + timedelta(minutes=45),
        )
        db_session.add(dummy_inc)
        await db_session.flush()
        v = IncidentVote(
            incident_id=dummy_inc.id,
            user_id=voter.id,
            vote=VoteType.confirm,
            voter_location=WKTElement("POINT(77.5946 12.9716)", srid=4326),
            created_at=now,
        )
        db_session.add(v)
    await db_session.commit()

    # 31st vote exceeds MAX_VOTES_PER_HOUR -> 429
    v_resp = await auth_client.post(
        f"/api/incidents/{target_inc.id}/vote",
        json={"vote": "confirm", "voter_lat": 12.9716, "voter_lng": 77.5946},
        headers={"Authorization": f"Bearer {v_token}"},
    )
    assert v_resp.status_code == 429
    assert "Retry-After" in v_resp.headers


# ---------------------------------------------------------------------------
# 11. Concurrent Votes Do Not Double Count (SELECT FOR UPDATE)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_votes_do_not_double_count(
    test_engine, db_session: AsyncSession
) -> None:
    reporter, _ = await create_test_user(db_session, name="Reporter")
    incident = Incident(
        reporter_id=reporter.id,
        location=WKTElement("POINT(77.5946 12.9716)", srid=4326),
        incident_type=IncidentType.accident,
        status=IncidentStatus.pending,
        confirmations=1,
        rejections=0,
        trust_score=1.0,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=45),
    )
    db_session.add(incident)
    await db_session.commit()
    await db_session.refresh(incident)

    # Create 5 distinct voters
    voters = [await create_test_user(db_session, name=f"Voter {i}") for i in range(5)]

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def _cast_vote(voter_user: User):
        from app.services.incident_service import vote_incident
        async with session_maker() as s:
            await vote_incident(
                db=s,
                user=voter_user,
                incident_id=incident.id,
                vote_type=VoteType.confirm,
                voter_lat=12.9717,
                voter_lng=77.5946,
            )

    # Run 5 concurrent votes
    await asyncio.gather(*[_cast_vote(v[0]) for v in voters])

    await db_session.refresh(incident)
    # Total confirmations should be exactly 1 initial + 5 votes = 6
    assert incident.confirmations == 6
    assert incident.trust_score == 6.0


# ---------------------------------------------------------------------------
# 12. Nearby Query Filtering
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_nearby_query_filtering(auth_client: AsyncClient, db_session: AsyncSession) -> None:
    user, token = await create_test_user(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # Incident A in Bengaluru Central (within 1km)
    await auth_client.post(
        "/api/incidents",
        json={"lat": 12.9716, "lng": 77.5946, "type": "accident"},
        headers=headers,
    )

    # Query within 2000m
    resp = await auth_client.get(
        "/api/incidents/nearby?lat=12.9720&lng=77.5946&radius_m=2000",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    first = data["incidents"][0]
    assert first["distance_m"] < 2000.0
    assert first["seconds_remaining"] > 0
    assert first["user_voted"] is True


# ---------------------------------------------------------------------------
# 13. WebSocket: Auth Timeout
# ---------------------------------------------------------------------------
def test_websocket_auth_timeout(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WS_AUTH_TIMEOUT_S", 0.2)
    client = TestClient(app)
    # Connect and do not send auth message immediately; test server close code
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()
    assert exc.value.code == 4401


# ---------------------------------------------------------------------------
# 14. WebSocket: Bad Token
# ---------------------------------------------------------------------------
def test_websocket_bad_token() -> None:
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "auth", "token": "not_a_valid_jwt_token"})
            ws.receive_json()
    assert exc.value.code == 4401


def test_websocket_auth_and_subscribe_success() -> None:
    client = TestClient(app)
    token = create_access_token(subject=str(uuid.uuid4()), role="civilian")
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": token})
        auth_ack = ws.receive_json()
        assert auth_ack["type"] == "auth.success"

        ws.send_json({"type": "subscribe", "lat": 12.9716, "lng": 77.5946, "radius_m": 5000})
        sub_ack = ws.receive_json()
        assert sub_ack["type"] == "subscribe.success"
        assert sub_ack["radius_m"] == 5000.0

        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"


# ---------------------------------------------------------------------------
# 15. WebSocket: Area Filtering (Far Away User Receives Nothing)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_websocket_area_filtering() -> None:
    # Test realtime manager area filtering directly
    # Client 1 in Bengaluru (radius 1000m)
    # Client 2 in Mumbai (radius 1000m)
    # Point in Bengaluru
    bengaluru_lat, bengaluru_lng = 12.9716, 77.5946
    mumbai_lat, mumbai_lng = 19.0760, 72.8777

    class DummyWS:
        def __init__(self):
            self.received = []

        async def send_json(self, data):
            self.received.append(data)

    ws_bengaluru = DummyWS()
    ws_mumbai = DummyWS()

    await realtime_manager.connect(ws_bengaluru, user_id="user_bengaluru", role="civilian")
    await realtime_manager.connect(ws_mumbai, user_id="user_mumbai", role="civilian")

    await realtime_manager.subscribe_area(ws_bengaluru, bengaluru_lat, bengaluru_lng, 1000.0)
    await realtime_manager.subscribe_area(ws_mumbai, mumbai_lat, mumbai_lng, 1000.0)

    # Broadcast event at Bengaluru location
    test_msg = create_realtime_message("incident.created", {"id": "test-inc-1"})
    delivered = await realtime_manager.broadcast_to_area(bengaluru_lat, bengaluru_lng, test_msg)

    assert delivered == 1
    assert len(ws_bengaluru.received) == 1
    assert ws_bengaluru.received[0]["type"] == "incident.created"
    assert len(ws_mumbai.received) == 0  # Mumbai user received NOTHING

    await realtime_manager.disconnect(ws_bengaluru)
    await realtime_manager.disconnect(ws_mumbai)


# ---------------------------------------------------------------------------
# 16. WebSocket: Connection Limit (WS_MAX_CONNECTIONS_PER_USER)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_websocket_connection_limit() -> None:
    user_id = f"user_{uuid.uuid4().hex[:8]}"

    class MockWS:
        pass

    sockets = [MockWS() for _ in range(settings.WS_MAX_CONNECTIONS_PER_USER)]
    for ws in sockets:
        ok = await realtime_manager.connect(ws, user_id=user_id, role="civilian")
        assert ok is True

    # 4th connection exceeds limit of 3
    overflow_ws = MockWS()
    rejected = await realtime_manager.connect(overflow_ws, user_id=user_id, role="civilian")
    assert rejected is False

    # Clean up
    for ws in sockets:
        await realtime_manager.disconnect(ws)
