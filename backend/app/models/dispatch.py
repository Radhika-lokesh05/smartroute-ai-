import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.incident import Incident
    from app.models.ambulance import Ambulance
    from app.models.hospital import Hospital


class DispatchStatus(str, enum.Enum):
    """Ambulance dispatch status progression."""
    offered = "offered"
    accepted = "accepted"
    en_route_to_scene = "en_route_to_scene"
    at_scene = "at_scene"
    to_hospital = "to_hospital"
    completed = "completed"
    declined = "declined"
    expired = "expired"
    cancelled = "cancelled"


ACTIVE_DISPATCH_STATUSES = {
    DispatchStatus.offered,
    DispatchStatus.accepted,
    DispatchStatus.en_route_to_scene,
    DispatchStatus.at_scene,
    DispatchStatus.to_hospital,
}


class Dispatch(Base):
    __tablename__ = "dispatches"

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
    ambulance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ambulances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[DispatchStatus] = mapped_column(
        Enum(DispatchStatus, name="dispatch_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=DispatchStatus.offered,
        nullable=False,
        index=True,
    )
    offered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    arrived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    picked_up_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    eta_to_scene_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    eta_to_hospital_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    emergency_type: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    offer_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_simulated: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True, index=True)

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident")
    ambulance: Mapped["Ambulance"] = relationship("Ambulance")
    hospital: Mapped[Optional["Hospital"]] = relationship("Hospital")


# Partial indexes enforcing at most ONE active dispatch per incident and per ambulance
Index(
    "ix_dispatches_active_incident",
    Dispatch.incident_id,
    unique=True,
    postgresql_where=(Dispatch.status.in_([
        DispatchStatus.offered,
        DispatchStatus.accepted,
        DispatchStatus.en_route_to_scene,
        DispatchStatus.at_scene,
        DispatchStatus.to_hospital,
    ])),
)

Index(
    "ix_dispatches_active_ambulance",
    Dispatch.ambulance_id,
    unique=True,
    postgresql_where=(Dispatch.status.in_([
        DispatchStatus.accepted,
        DispatchStatus.en_route_to_scene,
        DispatchStatus.at_scene,
        DispatchStatus.to_hospital,
    ])),
)
