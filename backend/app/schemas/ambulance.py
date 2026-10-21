import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.ambulance import AmbulanceStatus
from app.schemas.user import UserResponse


class AmbulanceCreate(BaseModel):
    """Admin payload to create an ambulance operator account and vehicle record."""
    name: str = Field(..., min_length=1, max_length=255, description="Operator or fleet name")
    email: EmailStr = Field(..., description="Ambulance account email")
    password: str = Field(..., min_length=8, description="Account password (min 8 characters)")
    plate_number: str = Field(..., min_length=1, max_length=64, description="Vehicle registration plate")


class AmbulanceVerify(BaseModel):
    """Payload to toggle ambulance verification."""
    is_verified: bool = Field(True, description="Verification status flag")


class AmbulanceStatusUpdate(BaseModel):
    """Payload for ambulance status update."""
    status: str = Field(..., description="available | offline")


class AmbulanceResponse(BaseModel):
    """Ambulance details response schema."""
    id: uuid.UUID
    user_id: uuid.UUID
    plate_number: str
    status: AmbulanceStatus
    is_verified: bool
    last_seen_at: Optional[datetime] = None
    user: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)
