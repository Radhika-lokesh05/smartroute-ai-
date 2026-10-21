import re
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models.user import UserRole


class UserRegister(BaseModel):
    """Payload for public user registration. Role is intentionally ignored if provided."""
    name: str = Field(..., min_length=1, max_length=255, description="Full name of user")
    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    role: Optional[str] = Field(None, description="Ignored: registration always creates a civilian")

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        cleaned = re.sub(r"<[^>]+>", "", str(v)).strip()
        return cleaned[:255]


class UserLogin(BaseModel):
    """Payload for user authentication."""
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")


class UserResponse(BaseModel):
    """Public user profile data. Never includes password_hash."""
    id: uuid.UUID
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """JWT bearer token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
