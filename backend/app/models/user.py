import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ambulance import Ambulance
    from app.models.incident import Incident, IncidentVote


class UserRole(str, enum.Enum):
    """User authorization roles."""
    civilian = "civilian"
    ambulance = "ambulance"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", values_callable=lambda x: [e.value for e in x]),
        default=UserRole.civilian,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    ambulance: Mapped[Optional["Ambulance"]] = relationship(
        "Ambulance",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    incidents: Mapped[List["Incident"]] = relationship(
        "Incident",
        back_populates="reporter",
        foreign_keys="Incident.reporter_id",
    )
    votes: Mapped[List["IncidentVote"]] = relationship(
        "IncidentVote",
        back_populates="user",
        cascade="all, delete-orphan",
    )
