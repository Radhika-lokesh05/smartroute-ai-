import enum
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, List, Optional
from geoalchemy2 import Geography
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class IncidentType(str, enum.Enum):
    """Types of road incidents reported."""
    accident = "accident"
    blockage = "blockage"
    hazard = "hazard"


class IncidentStatus(str, enum.Enum):
    """Validation lifecycle states for an incident."""
    pending = "pending"
    validated = "validated"
    resolved = "resolved"
    expired = "expired"


class VoteType(str, enum.Enum):
    """Community consensus vote on an incident."""
    confirm = "confirm"
    reject = "reject"


def default_incident_expiration() -> datetime:
    """Default expiration is 45 minutes from creation."""
    return datetime.now(timezone.utc) + timedelta(minutes=45)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    reporter_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    incident_type: Mapped[IncidentType] = mapped_column(
        Enum(IncidentType, name="incident_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus, name="incident_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=IncidentStatus.pending,
        nullable=False,
    )
    confirmations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trust_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=default_incident_expiration,
        nullable=False,
    )
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    expiry_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_simulated: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
        index=True,
    )

    reporter: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="incidents",
        foreign_keys=[reporter_id],
    )
    resolved_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[resolved_by_id],
    )
    votes: Mapped[List["IncidentVote"]] = relationship(
        "IncidentVote",
        back_populates="incident",
        cascade="all, delete-orphan",
    )


class IncidentVote(Base):
    __tablename__ = "incident_votes"
    __table_args__ = (
        UniqueConstraint("incident_id", "user_id", name="uq_incident_user_vote"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vote: Mapped[VoteType] = mapped_column(
        Enum(VoteType, name="vote_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    voter_location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    incident: Mapped["Incident"] = relationship("Incident", back_populates="votes")
    user: Mapped["User"] = relationship("User", back_populates="votes")
