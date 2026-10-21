"""Hospital API endpoints for emergency triage and nearest facility lookup."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.hospital import HospitalNearbyResponse
from app.services.hospital_service import hospital_service

router = APIRouter(prefix="/api/hospitals", tags=["Hospitals"])


@router.get("/nearby", response_model=HospitalNearbyResponse)
async def get_nearby_hospitals(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude in range [-90.0, 90.0]"),
    lng: float = Query(..., ge=-180.0, le=180.0, description="Longitude in range [-180.0, 180.0]"),
    emergency_type: Optional[str] = Query(
        None,
        description="Optional emergency specialization: general | trauma | cardiac | burns | maternity | pediatric",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> HospitalNearbyResponse:
    """
    Search and rank nearest emergency hospitals to specified coordinates.
    Incorporates traffic and incident delays for top candidates.
    Supports both guest emergency access and authenticated users.
    """
    return await hospital_service.rank_hospitals(
        origin=(lat, lng),
        emergency_type=emergency_type,
        db=db,
    )
