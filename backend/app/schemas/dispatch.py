"""Pydantic schemas for emergency ambulance dispatching."""
import re
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DispatchTriggerRequest(BaseModel):
    incident_id: uuid.UUID = Field(..., description="Target accident or hazard incident ID")
    emergency_type: str = Field("general", description="general | trauma | cardiac | burns | maternity | pediatric")


class DispatchProgressUpdate(BaseModel):
    status: str = Field(..., description="at_scene | to_hospital | completed | cancelled")
    hospital_id: Optional[uuid.UUID] = Field(None, description="Destination hospital ID when en route to hospital")


class DispatchDeclineRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=255, description="Optional decline explanation")

    @field_validator("reason", mode="before")
    @classmethod
    def sanitize_reason(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = re.sub(r"<[^>]+>", "", str(v)).strip()
        return cleaned[:255] if cleaned else None


class DispatchResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    ambulance_id: uuid.UUID
    hospital_id: Optional[uuid.UUID] = None
    status: str
    offered_at: datetime
    accepted_at: Optional[datetime] = None
    arrived_at: Optional[datetime] = None
    picked_up_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    eta_to_scene_s: float
    eta_to_hospital_s: float
    emergency_type: str
    offer_number: int

    model_config = ConfigDict(from_attributes=True)
