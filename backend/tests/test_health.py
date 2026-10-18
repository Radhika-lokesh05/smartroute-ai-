import pytest
from unittest.mock import patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_success(client: AsyncClient) -> None:
    """Verify that GET /health responds with 200 OK and expected structure."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "SmartRoute AI Backend"
    assert "database" in data
    assert data["database"] in ("connected", "unreachable")


@pytest.mark.asyncio
async def test_health_check_resilience_when_database_unreachable(client: AsyncClient) -> None:
    """Verify that GET /health does NOT crash if the database throws an exception or is unreachable."""
    with patch(
        "app.api.health.check_database_connection",
        return_value=(False, "Database unreachable: ConnectionRefusedError"),
    ):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "unreachable"
        assert "ConnectionRefusedError" in data["database_detail"]
