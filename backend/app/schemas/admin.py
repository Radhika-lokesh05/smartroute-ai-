import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.ambulance import AmbulanceStatus
from app.models.user import UserRole
from app.schemas.user import UserResponse


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    actor_user_id: Optional[uuid.UUID] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int


class AdminUserListResponse(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    page_size: int


class AdminUserActiveUpdate(BaseModel):
    is_active: bool = Field(..., description="Active status flag")


class AdminAmbulanceResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    plate_number: str
    status: AmbulanceStatus
    is_verified: bool
    last_seen_at: Optional[datetime] = None
    is_stale: bool = False
    user: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)


class AdminAmbulanceListResponse(BaseModel):
    items: List[AdminAmbulanceResponse]
    total: int
    page: int
    page_size: int


class AdminIncidentForceResolve(BaseModel):
    reason: Optional[str] = Field("Force-resolved by admin", max_length=200)


class AdminManualDispatch(BaseModel):
    incident_id: uuid.UUID
    ambulance_id: uuid.UUID
    emergency_type: str = Field("general", max_length=64)


class AdminDispatchCancel(BaseModel):
    reason: Optional[str] = Field("Cancelled by admin", max_length=200)
