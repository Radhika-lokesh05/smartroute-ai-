from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema for service health check response."""
    status: str = Field(..., description="Overall service status (e.g., 'ok')")
    service: str = Field("SmartRoute AI Backend", description="Service identifier")
    database: str = Field(..., description="Database connection status ('connected' or 'unreachable')")
    database_detail: Optional[str] = Field(None, description="Detailed diagnostic message for database status")
