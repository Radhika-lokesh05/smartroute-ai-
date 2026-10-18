from fastapi import APIRouter
from app.schemas.health import HealthResponse
from app.core.database import check_database_connection

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """
    Health check endpoint.
    Probes database availability without failing or raising exceptions if unreachable.
    Always returns HTTP 200 with service and database connection details.
    """
    is_connected, detail_msg = await check_database_connection(timeout_seconds=2.0)

    return HealthResponse(
        status="ok",
        service="SmartRoute AI Backend",
        database="connected" if is_connected else "unreachable",
        database_detail=detail_msg,
    )
