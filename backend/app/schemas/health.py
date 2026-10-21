from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Schema for liveness probe response."""
    status: str = Field("ok", description="Overall service status (e.g., 'ok')")
    service: str = Field("SmartRoute AI Backend", description="Service identifier")
    database: Optional[str] = Field("alive", description="Liveness flag")
    database_detail: Optional[str] = Field(None, description="Diagnostic detail (if any)")


class ReadyResponse(BaseModel):
    """Schema for readiness probe response."""
    model_config = ConfigDict(protected_namespaces=())

    status: str = Field(..., description="Readiness status ('ready' or 'not_ready')")
    database: str = Field(..., description="Database connection status ('connected' or 'unreachable')")
    model_available: bool = Field(..., description="Whether ML traffic model artifacts are loaded")
    migrations: str = Field(..., description="Database migration status ('up_to_date', 'pending', or 'unknown')")
