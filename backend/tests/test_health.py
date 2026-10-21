import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_liveness_check(client: AsyncClient) -> None:
    """Verify that GET /health responds with 200 OK and liveness structure without touching the DB."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "SmartRoute AI Backend"
    assert "database" in data


@pytest.mark.asyncio
async def test_ready_check_success(client: AsyncClient) -> None:
    """Verify that GET /ready returns 200 OK with database, model_available, and migration status."""
    with patch(
        "app.api.health.check_database_readiness",
        new_callable=AsyncMock,
        return_value=(True, "connected", "up_to_date"),
    ):
        response = await client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"
        assert "model_available" in data
        assert data["migrations"] == "up_to_date"


@pytest.mark.asyncio
async def test_ready_check_resilience_when_database_unreachable(client: AsyncClient) -> None:
    """Verify that GET /ready returns 503 when the database is unreachable without leaking credentials."""
    with patch(
        "app.api.health.check_database_readiness",
        new_callable=AsyncMock,
        return_value=(False, "unreachable", "unknown"),
    ):
        response = await client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "unreachable"
        assert data["migrations"] == "unknown"
