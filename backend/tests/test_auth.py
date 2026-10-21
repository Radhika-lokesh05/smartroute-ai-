import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserRole
from app.core.security import get_password_hash


@pytest.mark.asyncio
async def test_register_success(auth_client: AsyncClient) -> None:
    """Verify that public registration successfully creates a civilian account."""
    payload = {
        "name": "Jane Civilian",
        "email": "jane@example.com",
        "password": "securepassword123",
    }
    response = await auth_client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Jane Civilian"
    assert data["email"] == "jane@example.com"
    assert data["role"] == "civilian"
    assert data["is_active"] is True
    assert "password_hash" not in data
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(auth_client: AsyncClient) -> None:
    """Verify that registering with an already existing email returns 400 Bad Request."""
    payload = {
        "name": "Duplicate User",
        "email": "dup@example.com",
        "password": "password123",
    }
    first_resp = await auth_client.post("/api/auth/register", json=payload)
    assert first_resp.status_code == 201

    second_resp = await auth_client.post("/api/auth/register", json=payload)
    assert second_resp.status_code == 400
    assert "already registered" in second_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_cannot_create_admin(auth_client: AsyncClient) -> None:
    """Verify that public registration strictly ignores any role field and assigns civilian."""
    payload = {
        "name": "Malicious User",
        "email": "malicious@example.com",
        "password": "password123",
        "role": "admin",
    }
    response = await auth_client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "civilian"
    assert data["role"] != "admin"


@pytest.mark.asyncio
async def test_login_success(auth_client: AsyncClient) -> None:
    """Verify that valid login credentials return a JWT bearer access token."""
    register_payload = {
        "name": "Login Tester",
        "email": "login@example.com",
        "password": "loginpassword123",
    }
    reg_resp = await auth_client.post("/api/auth/register", json=register_payload)
    assert reg_resp.status_code == 201

    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "loginpassword123"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login@example.com"
    assert data["user"]["role"] == "civilian"


@pytest.mark.asyncio
async def test_login_failure(auth_client: AsyncClient) -> None:
    """Verify that invalid password or unregistered email returns 401 Unauthorized."""
    # Non-existent user
    resp1 = await auth_client.post(
        "/api/auth/login",
        json={"email": "nonexistent@example.com", "password": "password123"},
    )
    assert resp1.status_code == 401

    # Wrong password for existing user
    await auth_client.post(
        "/api/auth/register",
        json={"name": "Alice", "email": "alice@example.com", "password": "correct_password123"},
    )
    resp2 = await auth_client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wrong_password123"},
    )
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_me_with_and_without_token(auth_client: AsyncClient) -> None:
    """Verify that /me succeeds with valid token and rejects unauthorized requests."""
    # Without token
    resp_no_token = await auth_client.get("/api/auth/me")
    assert resp_no_token.status_code == 401

    # With invalid token
    resp_invalid = await auth_client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid_garbage_token"},
    )
    assert resp_invalid.status_code == 401

    # With valid token
    await auth_client.post(
        "/api/auth/register",
        json={"name": "Token Tester", "email": "token@example.com", "password": "password123"},
    )
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": "token@example.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]

    resp_auth = await auth_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_auth.status_code == 200
    data = resp_auth.json()
    assert data["email"] == "token@example.com"
    assert data["name"] == "Token Tester"


@pytest.mark.asyncio
async def test_civilian_cannot_call_admin_endpoints(auth_client: AsyncClient) -> None:
    """Verify that a civilian user cannot call admin endpoints and receives 403 Forbidden."""
    await auth_client.post(
        "/api/auth/register",
        json={"name": "Civ User", "email": "civ@example.com", "password": "password123"},
    )
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": "civ@example.com", "password": "password123"},
    )
    civ_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {civ_token}"}

    # Attempt ambulance creation
    amb_resp = await auth_client.post(
        "/api/admin/ambulances",
        json={
            "name": "Medic One",
            "email": "medic@example.com",
            "password": "password123",
            "plate_number": "MEDIC-999",
        },
        headers=headers,
    )
    assert amb_resp.status_code == 403

    # Attempt ambulance verification
    verify_resp = await auth_client.patch(
        f"/api/admin/ambulances/{uuid.uuid4()}/verify",
        json={"is_verified": True},
        headers=headers,
    )
    assert verify_resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_create_and_verify_ambulance(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify that an administrator can create and verify ambulance records."""
    # Seed an admin directly in the test database
    admin = User(
        name="Admin Chief",
        email="chief@smartroute.ai",
        password_hash=get_password_hash("adminpassword123"),
        role=UserRole.admin,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()

    # Login as admin
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": "chief@smartroute.ai", "password": "adminpassword123"},
    )
    assert login_resp.status_code == 200
    admin_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create ambulance
    amb_payload = {
        "name": "Metro Ambulance 101",
        "email": "metro101@ambulances.example.com",
        "password": "medicpassword123",
        "plate_number": "EMS-101",
    }
    create_resp = await auth_client.post(
        "/api/admin/ambulances",
        json=amb_payload,
        headers=headers,
    )
    assert create_resp.status_code == 201
    amb_data = create_resp.json()
    assert amb_data["plate_number"] == "EMS-101"
    assert amb_data["status"] == "offline"
    assert amb_data["is_verified"] is False
    assert amb_data["user"]["role"] == "ambulance"
    ambulance_id = amb_data["id"]

    # Verify ambulance
    verify_resp = await auth_client.patch(
        f"/api/admin/ambulances/{ambulance_id}/verify",
        json={"is_verified": True},
        headers=headers,
    )
    assert verify_resp.status_code == 200
    verified_data = verify_resp.json()
    assert verified_data["id"] == ambulance_id
    assert verified_data["is_verified"] is True
