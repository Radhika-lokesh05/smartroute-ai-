from fastapi import APIRouter, Response, status
from app.schemas.health import HealthResponse, ReadyResponse
from app.core.database import check_database_readiness
from app.services.traffic_model import traffic_model_service

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """
    Liveness probe endpoint.
    Verifies that the API service process is alive and responding.
    Does not query the database to prevent cascade failures or false-positive pod restarts.
    """
    return HealthResponse(
        status="ok",
        service="SmartRoute AI Backend",
        database="alive",
        database_detail=None,
    )


@router.get("/ready", response_model=ReadyResponse)
async def get_ready(response: Response) -> ReadyResponse:
    """
    Readiness probe endpoint.
    Checks database connectivity, ML model availability, and migration status.
    Returns HTTP 200 when ready to serve traffic, or HTTP 503 if dependencies are unreachable.
    Never exposes internal connection strings, credentials, or stack traces.
    """
    is_ready, db_status, migration_status = await check_database_readiness(timeout_seconds=2.0)
    model_avail = bool(traffic_model_service.model_available)

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(
            status="not_ready",
            database=db_status,
            model_available=model_avail,
            migrations=migration_status,
        )

    return ReadyResponse(
        status="ready",
        database=db_status,
        model_available=model_avail,
        migrations=migration_status,
    )
