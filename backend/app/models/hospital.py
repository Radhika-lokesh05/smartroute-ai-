import uuid
from typing import Any, List, Optional
from geoalchemy2 import Geography
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Hospital(Base):
    __tablename__ = "hospitals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    has_emergency: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    specialties: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
    )
    emergency_types: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=lambda: ["general"],
        comment="general, trauma, cardiac, burns, maternity, pediatric",
    )
    is_24x7: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # SIMULATED data: Estimated emergency bed capacity for demonstration
    simulated_beds: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="SIMULATED data: Estimated emergency bed capacity for demonstration",
    )
    beds_simulated: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Always true, never shown as real beds",
    )
    source: Mapped[str] = mapped_column(
        String(32),
        default="osm",
        nullable=False,
    )
    osm_attribution: Mapped[str] = mapped_column(
        String(255),
        default="© OpenStreetMap contributors",
        nullable=False,
    )
    osm_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
        index=True,
    )
