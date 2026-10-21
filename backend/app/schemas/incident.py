import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from app.models.incident import IncidentType, IncidentStatus, VoteType


class IncidentCreate(BaseModel):
    """Payload to create or report a new incident."""
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude between -90 and 90")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitude between -180 and 180")
    type: IncidentType = Field(..., description="Type of incident: accident, blockage, hazard")
    note: Optional[str] = Field(None, max_length=200, description="Optional description/note up to 200 chars")

    @field_validator("note", mode="before")
    @classmethod
    def sanitize_note(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = str(v).strip()
        if not cleaned:
            return None
        # Remove any HTML tags for XSS hygiene
        cleaned = re.sub(r"<[^>]+>", "", cleaned)
        return cleaned[:200]


class IncidentVoteCreate(BaseModel):
    """Payload to vote on an existing incident."""
    vote: VoteType = Field(..., description="'confirm' or 'reject'")
    voter_lat: float = Field(..., ge=-90.0, le=90.0, description="Current voter latitude")
    voter_lng: float = Field(..., ge=-180.0, le=180.0, description="Current voter longitude")


class IncidentPublicResponse(BaseModel):
    """
    Public representation of a road incident.
    Never exposes reporter email, user ID, or sensitive personal data.
    """
    id: uuid.UUID
    incident_type: IncidentType
    status: IncidentStatus
    lat: float
    lng: float
    confirmations: int
    rejections: int
    trust_score: float
    created_at: datetime
    expires_at: datetime
    validated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    seconds_remaining: int = 0
    note: Optional[str] = None
    user_voted: bool = False
    user_vote: Optional[VoteType] = None
    distance_m: Optional[float] = None

    model_config = {
        "from_attributes": True,
    }


class IncidentListResponse(BaseModel):
    """List response for nearby incidents."""
    total: int
    incidents: List[IncidentPublicResponse]
