import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from geoalchemy2 import Geography
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class AmbulanceStatus(str, enum.Enum):
    """Ambulance availability status."""
    offline = "offline"
    available = "available"
    busy = "busy"


class Ambulance(Base):
    __tablename__ = "ambulances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    plate_number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[AmbulanceStatus] = mapped_column(
        Enum(AmbulanceStatus, name="ambulance_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=AmbulanceStatus.offline,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_location: Mapped[Optional[Any]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="ambulance")
