"""Ambulance operator API endpoints for status management and self-inspection."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.ambulance import Ambulance, AmbulanceStatus
from app.models.user import User, UserRole
from app.schemas.ambulance import AmbulanceResponse, AmbulanceStatusUpdate

router = APIRouter(prefix="/api/ambulance", tags=["Ambulance"])


@router.get("/me", response_model=AmbulanceResponse)
async def get_my_ambulance_record(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AmbulanceResponse:
    """Return the ambulance record for the authenticated ambulance operator."""
    if current_user.role != UserRole.ambulance:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ambulance accounts may access ambulance profile.",
        )

    stmt = select(Ambulance).where(Ambulance.user_id == current_user.id).options(selectinload(Ambulance.user))
    res = await db.execute(stmt)
    ambulance = res.scalar_one_or_none()

    if not ambulance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ambulance profile linked to this user account.",
        )

    return AmbulanceResponse.model_validate(ambulance)


@router.patch("/status", response_model=AmbulanceResponse)
async def update_ambulance_status(
    payload: AmbulanceStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AmbulanceResponse:
    """
    Update ambulance status to 'available' or 'offline'.
    Status 'busy' can only be set by the dispatch service.
    Only verified ambulances may update status.
    """
    if current_user.role != UserRole.ambulance:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ambulance personnel may update status.",
        )

    stmt = select(Ambulance).where(Ambulance.user_id == current_user.id).options(selectinload(Ambulance.user))
    res = await db.execute(stmt)
    ambulance = res.scalar_one_or_none()

    if not ambulance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ambulance record not found.",
        )

    if not ambulance.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only verified ambulances may update status.",
        )

    target_status = payload.status.strip().lower()
    if target_status == "busy":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status 'busy' can only be set by the dispatch system.",
        )

    if target_status not in ("available", "offline"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Status must be 'available' or 'offline'.",
        )

    ambulance.status = AmbulanceStatus(target_status)
    await db.commit()
    await db.refresh(ambulance)

    return AmbulanceResponse.model_validate(ambulance)
