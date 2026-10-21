"""API endpoints for emergency ambulance dispatch management."""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.ambulance import Ambulance
from app.models.dispatch import ACTIVE_DISPATCH_STATUSES, Dispatch
from app.models.user import User, UserRole
from app.schemas.dispatch import (
    DispatchDeclineRequest,
    DispatchProgressUpdate,
    DispatchResponse,
    DispatchTriggerRequest,
)
from app.services.dispatch_service import dispatch_service

router = APIRouter(prefix="/api/dispatches", tags=["Dispatches"])


@router.post("/trigger", response_model=DispatchResponse)
async def trigger_emergency_dispatch(
    payload: DispatchTriggerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DispatchResponse:
    """
    Trigger emergency dispatch offer to the nearest verified, available ambulance.
    Available to administrators and verified ambulance operators.
    """
    if current_user.role not in (UserRole.admin, UserRole.ambulance):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators or emergency personnel may trigger dispatches.",
        )

    dispatch = await dispatch_service.trigger_dispatch(
        incident_id=payload.incident_id,
        db=db,
        emergency_type=payload.emergency_type,
    )

    if not dispatch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No available verified ambulances within dispatch radius.",
        )

    return DispatchResponse.model_validate(dispatch)


@router.post("/{id}/accept", response_model=DispatchResponse)
async def accept_dispatch(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DispatchResponse:
    """Ambulance operator accepts dispatch offer."""
    if current_user.role != UserRole.ambulance:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ambulance accounts may accept dispatch offers.",
        )

    dispatch = await dispatch_service.accept_dispatch(
        dispatch_id=id,
        user_id=current_user.id,
        db=db,
    )
    return DispatchResponse.model_validate(dispatch)


@router.post("/{id}/decline", response_model=DispatchResponse)
async def decline_dispatch(
    id: uuid.UUID,
    payload: DispatchDeclineRequest = DispatchDeclineRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DispatchResponse:
    """Ambulance operator declines dispatch offer."""
    if current_user.role != UserRole.ambulance:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ambulance accounts may decline dispatch offers.",
        )

    dispatch = await dispatch_service.decline_dispatch(
        dispatch_id=id,
        user_id=current_user.id,
        db=db,
        reason=payload.reason,
    )
    return DispatchResponse.model_validate(dispatch)


@router.patch("/{id}/progress", response_model=DispatchResponse)
async def update_dispatch_progress(
    id: uuid.UUID,
    payload: DispatchProgressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DispatchResponse:
    """Advance dispatch status (at_scene | to_hospital | completed | cancelled)."""
    if current_user.role != UserRole.ambulance:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ambulance accounts may update dispatch progress.",
        )

    dispatch = await dispatch_service.update_progress(
        dispatch_id=id,
        user_id=current_user.id,
        new_status=payload.status,
        hospital_id=payload.hospital_id,
        db=db,
    )
    return DispatchResponse.model_validate(dispatch)


@router.get("/active", response_model=List[DispatchResponse])
async def get_active_dispatches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[DispatchResponse]:
    """Get active dispatches for current ambulance operator or all active dispatches for admin."""
    if current_user.role == UserRole.admin:
        stmt = (
            select(Dispatch)
            .where(Dispatch.status.in_(list(ACTIVE_DISPATCH_STATUSES)))
            .order_by(Dispatch.offered_at.desc())
        )
        res = await db.execute(stmt)
        dispatches = list(res.scalars().all())
        return [DispatchResponse.model_validate(d) for d in dispatches]

    if current_user.role == UserRole.ambulance:
        stmt_amb = select(Ambulance).where(Ambulance.user_id == current_user.id)
        res_amb = await db.execute(stmt_amb)
        ambulance = res_amb.scalar_one_or_none()
        if not ambulance:
            return []

        stmt = (
            select(Dispatch)
            .where(Dispatch.ambulance_id == ambulance.id)
            .where(Dispatch.status.in_(list(ACTIVE_DISPATCH_STATUSES)))
            .order_by(Dispatch.offered_at.desc())
        )
        res = await db.execute(stmt)
        dispatches = list(res.scalars().all())
        return [DispatchResponse.model_validate(d) for d in dispatches]

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")


@router.get("/{id}", response_model=DispatchResponse)
async def get_dispatch_details(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DispatchResponse:
    """Retrieve detailed dispatch information."""
    stmt = select(Dispatch).where(Dispatch.id == id)
    res = await db.execute(stmt)
    dispatch = res.scalar_one_or_none()

    if not dispatch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispatch not found.")

    return DispatchResponse.model_validate(dispatch)
