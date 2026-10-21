import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.ambulance import Ambulance, AmbulanceStatus
from app.models.incident import Incident, IncidentStatus
from app.models.dispatch import Dispatch, DispatchStatus
from app.schemas.ambulance import (
    AmbulanceCreate,
    AmbulanceVerify,
    AmbulanceResponse,
)
from app.schemas.user import UserResponse
from app.schemas.dispatch import DispatchResponse
from app.schemas.admin import (
    AdminAmbulanceListResponse,
    AdminAmbulanceResponse,
    AdminDispatchCancel,
    AdminIncidentForceResolve,
    AdminManualDispatch,
    AdminUserActiveUpdate,
    AdminUserListResponse,
    AuditLogListResponse,
    AuditLogResponse,
)
from app.services.audit_service import get_audit_logs, log_audit_event
from app.services.incident_service import (
    extract_incident_lat_lng,
    serialize_incident_dict,
)
from app.services.metrics_service import (
    export_metrics_csv,
    get_metrics_hotspots,
    get_metrics_summary,
    get_metrics_timeseries,
    get_model_info,
    validate_days,
)
from app.services.realtime import create_realtime_message, realtime_manager

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ============================================================================
# 1. Audit Log Endpoints
# ============================================================================

@router.get("/audit", response_model=AuditLogListResponse)
async def list_audit_logs(
    action: Optional[str] = Query(None, description="Filter by audit action"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=settings.ADMIN_PAGE_SIZE_MAX, description="Page size"),
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """Admin-only paginated query of system audit events."""
    items, total = await get_audit_logs(
        session=db,
        action=action,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================================================================
# 2. User Management Endpoints
# ============================================================================

@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    search: Optional[str] = Query(None, description="Search name or email"),
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=settings.ADMIN_PAGE_SIZE_MAX, description="Page size"),
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> AdminUserListResponse:
    """Admin-only user query with search and role filters. Never returns password_hash."""
    query = select(User)
    count_query = select(func.count(User.id))

    if search:
        search_filter = or_(
            User.name.ilike(f"%{search.strip()}%"),
            User.email.ilike(f"%{search.strip()}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)

    total = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(desc(User.created_at)).offset(offset).limit(page_size)
    result = await db.execute(query)
    users = list(result.scalars().all())

    return AdminUserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/users/{id}/active", response_model=UserResponse)
async def set_user_active_status(
    id: uuid.UUID,
    payload: AdminUserActiveUpdate,
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Deactivate or reactivate a user.
    - An admin cannot deactivate themselves.
    - An admin cannot deactivate the last remaining admin.
    - Deactivating a user immediately closes their active WebSockets and prevents JWT token validation.
    """
    stmt = select(User).where(User.id == id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Protection: Cannot deactivate self
    if id == current_admin.id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account.",
        )

    # Protection: Cannot deactivate the last remaining admin
    if user.role == UserRole.admin and not payload.is_active:
        admin_count_stmt = select(func.count(User.id)).where(
            User.role == UserRole.admin,
            User.is_active.is_(True),
        )
        active_admins = (await db.execute(admin_count_stmt)).scalar_one()
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last remaining active administrator.",
            )

    user.is_active = payload.is_active
    await db.commit()
    await db.refresh(user)

    action_name = "user.reactivated" if payload.is_active else "user.deactivated"
    await log_audit_event(
        session=db,
        action=action_name,
        entity_type="user",
        entity_id=str(user.id),
        actor_user_id=current_admin.id,
        details={"name": user.name, "email": user.email, "role": user.role.value},
    )
    await db.commit()

    # Immediately disconnect all active WebSockets for deactivated user
    if not payload.is_active:
        await realtime_manager.disconnect_user(str(user.id))

    return UserResponse.model_validate(user)


# ============================================================================
# 3. Ambulance Management Endpoints
# ============================================================================

@router.get("/ambulances", response_model=AdminAmbulanceListResponse)
async def list_ambulances(
    amb_status: Optional[AmbulanceStatus] = Query(None, alias="status", description="Filter by status"),
    is_verified: Optional[bool] = Query(None, description="Filter by verified status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=settings.ADMIN_PAGE_SIZE_MAX, description="Page size"),
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> AdminAmbulanceListResponse:
    """Admin-only ambulance list with status, verification, last seen, and stale flag."""
    query = select(Ambulance).options(selectinload(Ambulance.user))
    count_query = select(func.count(Ambulance.id))

    if amb_status:
        query = query.where(Ambulance.status == amb_status)
        count_query = count_query.where(Ambulance.status == amb_status)

    if is_verified is not None:
        query = query.where(Ambulance.is_verified.is_(is_verified))
        count_query = count_query.where(Ambulance.is_verified.is_(is_verified))

    total = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(Ambulance.plate_number.asc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    ambulances = list(result.scalars().all())

    now = datetime.now(timezone.utc)
    items = []
    for amb in ambulances:
        stale = False
        if amb.status != AmbulanceStatus.offline:
            if amb.last_seen_at is None:
                stale = True
            else:
                elapsed = (now - amb.last_seen_at).total_seconds()
                if elapsed > settings.AMBULANCE_LOCATION_STALE_S:
                    stale = True

        items.append(
            AdminAmbulanceResponse(
                id=amb.id,
                user_id=amb.user_id,
                plate_number=amb.plate_number,
                status=amb.status,
                is_verified=amb.is_verified,
                last_seen_at=amb.last_seen_at,
                is_stale=stale,
                user=UserResponse.model_validate(amb.user) if amb.user else None,
            )
        )

    return AdminAmbulanceListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/ambulances", response_model=AmbulanceResponse, status_code=status.HTTP_201_CREATED)
async def create_ambulance(
    payload: AmbulanceCreate,
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> AmbulanceResponse:
    """Admin-only endpoint to create an ambulance user account and vehicle record."""
    normalized_email = payload.email.lower().strip()
    normalized_plate = payload.plate_number.strip().upper()

    user_stmt = select(User).where(User.email == normalized_email)
    existing_user = (await db.execute(user_stmt)).scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered for another user",
        )

    amb_stmt = select(Ambulance).where(Ambulance.plate_number == normalized_plate)
    existing_amb = (await db.execute(amb_stmt)).scalar_one_or_none()
    if existing_amb is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ambulance plate number already registered",
        )

    amb_user = User(
        name=payload.name.strip(),
        email=normalized_email,
        password_hash=get_password_hash(payload.password),
        role=UserRole.ambulance,
        is_active=True,
    )
    db.add(amb_user)
    await db.flush()

    ambulance = Ambulance(
        user_id=amb_user.id,
        plate_number=normalized_plate,
        status=AmbulanceStatus.offline,
        is_verified=False,
    )
    db.add(ambulance)
    await db.commit()

    # Log audit entry (strictly omitting raw password or password_hash)
    await log_audit_event(
        session=db,
        action="ambulance.created",
        entity_type="ambulance",
        entity_id=str(ambulance.id),
        actor_user_id=current_admin.id,
        details={"plate_number": ambulance.plate_number, "email": amb_user.email},
    )
    await db.commit()

    result = await db.execute(
        select(Ambulance)
        .where(Ambulance.id == ambulance.id)
        .options(selectinload(Ambulance.user))
    )
    loaded_amb = result.scalar_one()

    return AmbulanceResponse(
        id=loaded_amb.id,
        user_id=loaded_amb.user_id,
        plate_number=loaded_amb.plate_number,
        status=loaded_amb.status,
        is_verified=loaded_amb.is_verified,
        last_seen_at=loaded_amb.last_seen_at,
        user=UserResponse.model_validate(loaded_amb.user) if loaded_amb.user else None,
    )


@router.patch("/ambulances/{id}/verify", response_model=AmbulanceResponse)
async def verify_ambulance(
    id: uuid.UUID,
    payload: AmbulanceVerify = AmbulanceVerify(is_verified=True),
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> AmbulanceResponse:
    """Admin-only endpoint to toggle verification status of an ambulance."""
    stmt = select(Ambulance).where(Ambulance.id == id).options(selectinload(Ambulance.user))
    result = await db.execute(stmt)
    ambulance = result.scalar_one_or_none()

    if ambulance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ambulance record not found",
        )

    ambulance.is_verified = payload.is_verified
    await db.commit()
    await db.refresh(ambulance)

    action = "ambulance.verified" if payload.is_verified else "ambulance.unverified"
    await log_audit_event(
        session=db,
        action=action,
        entity_type="ambulance",
        entity_id=str(ambulance.id),
        actor_user_id=current_admin.id,
        details={"plate_number": ambulance.plate_number, "is_verified": ambulance.is_verified},
    )
    await db.commit()

    return AmbulanceResponse(
        id=ambulance.id,
        user_id=ambulance.user_id,
        plate_number=ambulance.plate_number,
        status=ambulance.status,
        is_verified=ambulance.is_verified,
        last_seen_at=ambulance.last_seen_at,
        user=UserResponse.model_validate(ambulance.user) if ambulance.user else None,
    )


@router.patch("/ambulances/{id}/unverify", response_model=AmbulanceResponse)
async def unverify_ambulance(
    id: uuid.UUID,
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> AmbulanceResponse:
    """Admin-only endpoint to unverify an ambulance."""
    stmt = select(Ambulance).where(Ambulance.id == id).options(selectinload(Ambulance.user))
    result = await db.execute(stmt)
    ambulance = result.scalar_one_or_none()

    if ambulance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ambulance record not found",
        )

    ambulance.is_verified = False
    await db.commit()
    await db.refresh(ambulance)

    await log_audit_event(
        session=db,
        action="ambulance.unverified",
        entity_type="ambulance",
        entity_id=str(ambulance.id),
        actor_user_id=current_admin.id,
        details={"plate_number": ambulance.plate_number, "is_verified": False},
    )
    await db.commit()

    return AmbulanceResponse(
        id=ambulance.id,
        user_id=ambulance.user_id,
        plate_number=ambulance.plate_number,
        status=ambulance.status,
        is_verified=ambulance.is_verified,
        last_seen_at=ambulance.last_seen_at,
        user=UserResponse.model_validate(ambulance.user) if ambulance.user else None,
    )


# ============================================================================
# 4. Incident & Dispatch Admin Controls
# ============================================================================

@router.post("/incidents/{id}/resolve")
async def force_resolve_incident(
    id: uuid.UUID,
    payload: AdminIncidentForceResolve = AdminIncidentForceResolve(),
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Admin-only endpoint to force-resolve an incident."""
    stmt = select(Incident).where(Incident.id == id)
    incident = (await db.execute(stmt)).scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    now = datetime.now(timezone.utc)
    incident.status = IncidentStatus.resolved
    incident.resolved_at = now
    incident.resolved_by_id = current_admin.id
    if payload.reason:
        incident.note = payload.reason
    await db.commit()
    await db.refresh(incident)

    await log_audit_event(
        session=db,
        action="incident.force_resolved",
        entity_type="incident",
        entity_id=str(incident.id),
        actor_user_id=current_admin.id,
        details={"reason": payload.reason},
    )
    await db.commit()

    # Realtime notification
    try:
        lat, lng = extract_incident_lat_lng(incident.location)
        await realtime_manager.broadcast_to_area(
            lat,
            lng,
            create_realtime_message("incident.resolved", serialize_incident_dict(incident, lat, lng)),
        )
    except Exception:
        pass

    return {"message": "Incident force-resolved successfully", "incident_id": str(incident.id)}


@router.post("/dispatches/manual", response_model=DispatchResponse)
async def manual_dispatch_assignment(
    payload: AdminManualDispatch,
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> DispatchResponse:
    """Admin-only endpoint to manually dispatch a specific verified ambulance to an incident."""
    inc_stmt = select(Incident).where(Incident.id == payload.incident_id)
    incident = (await db.execute(inc_stmt)).scalar_one_or_none()
    if not incident or incident.status in (IncidentStatus.resolved, IncidentStatus.expired):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incident not active")

    amb_stmt = select(Ambulance).where(Ambulance.id == payload.ambulance_id)
    ambulance = (await db.execute(amb_stmt)).scalar_one_or_none()
    if not ambulance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ambulance not found")
    if not ambulance.is_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ambulance is not verified")

    # Count prior offers for this incident
    past_offers_stmt = select(func.count(Dispatch.id)).where(Dispatch.incident_id == incident.id)
    offer_count = (await db.execute(past_offers_stmt)).scalar_one()

    new_dispatch = Dispatch(
        incident_id=incident.id,
        ambulance_id=ambulance.id,
        status=DispatchStatus.offered,
        offered_at=datetime.now(timezone.utc),
        emergency_type=payload.emergency_type,
        offer_number=offer_count + 1,
        is_simulated=bool(incident.is_simulated),
    )
    db.add(new_dispatch)
    await db.commit()
    await db.refresh(new_dispatch)

    await log_audit_event(
        session=db,
        action="dispatch.manual_assigned",
        entity_type="dispatch",
        entity_id=str(new_dispatch.id),
        actor_user_id=current_admin.id,
        details={
            "incident_id": str(incident.id),
            "ambulance_id": str(ambulance.id),
            "emergency_type": payload.emergency_type,
        },
    )
    await db.commit()

    # Notify ambulance and admins
    offer_msg = {
        "v": 1,
        "type": "dispatch.offered",
        "data": {
            "dispatch_id": str(new_dispatch.id),
            "incident_id": str(incident.id),
            "emergency_type": payload.emergency_type,
            "eta_to_scene_s": 0.0,
            "offer_number": new_dispatch.offer_number,
            "expires_in_s": int(settings.DISPATCH_OFFER_TIMEOUT_S),
        },
    }
    await realtime_manager.send_to_user(str(ambulance.user_id), offer_msg)
    await realtime_manager.send_to_role("admin", offer_msg)

    return DispatchResponse.model_validate(new_dispatch)


@router.post("/dispatches/{id}/cancel")
async def cancel_dispatch_admin(
    id: uuid.UUID,
    payload: AdminDispatchCancel = AdminDispatchCancel(),
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Admin-only endpoint to cancel a dispatch."""
    stmt = (
        select(Dispatch)
        .where(Dispatch.id == id)
        .options(selectinload(Dispatch.ambulance))
    )
    dispatch = (await db.execute(stmt)).scalar_one_or_none()
    if not dispatch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispatch not found")

    dispatch.status = DispatchStatus.cancelled
    if dispatch.ambulance:
        dispatch.ambulance.status = AmbulanceStatus.available

    await db.commit()
    await db.refresh(dispatch)

    await log_audit_event(
        session=db,
        action="dispatch.cancelled",
        entity_type="dispatch",
        entity_id=str(dispatch.id),
        actor_user_id=current_admin.id,
        details={"reason": payload.reason},
    )
    await db.commit()

    cancel_msg = {
        "v": 1,
        "type": "dispatch.cancelled",
        "data": {
            "dispatch_id": str(dispatch.id),
            "reason": payload.reason,
        },
    }
    if dispatch.ambulance:
        await realtime_manager.send_to_user(str(dispatch.ambulance.user_id), cancel_msg)
    await realtime_manager.send_to_role("admin", cancel_msg)

    return {"message": "Dispatch cancelled successfully", "dispatch_id": str(dispatch.id)}


@router.get("/dispatches", response_model=dict)
async def list_admin_dispatches(
    dispatch_status: Optional[str] = Query(None, alias="status", description="Status filter"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=settings.ADMIN_PAGE_SIZE_MAX, description="Page size"),
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Admin-only paginated listing of all dispatches."""
    query = select(Dispatch)
    count_query = select(func.count(Dispatch.id))

    if dispatch_status:
        query = query.where(Dispatch.status == dispatch_status)
        count_query = count_query.where(Dispatch.status == dispatch_status)

    total = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(desc(Dispatch.offered_at)).offset(offset).limit(page_size)
    result = await db.execute(query)
    dispatches = list(result.scalars().all())

    return {
        "items": [DispatchResponse.model_validate(d) for d in dispatches],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============================================================================
# 5. Metrics Endpoints
# ============================================================================

@router.get("/metrics/summary")
async def get_metrics_summary_endpoint(
    days: Optional[int] = Query(None, description="Time range in days (1-90)"),
    origin: str = Query("all", description="all | live | simulated"),
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Admin-only KPI metrics summary aggregated via SQL."""
    valid_days = validate_days(days)
    return await get_metrics_summary(session=db, days=valid_days, origin=origin)


@router.get("/metrics/timeseries")
async def get_metrics_timeseries_endpoint(
    days: Optional[int] = Query(None, description="Time range in days (1-90)"),
    bucket: str = Query("day", description="hour | day"),
    origin: str = Query("all", description="all | live | simulated"),
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Admin-only incident and dispatch counts per time bucket."""
    valid_days = validate_days(days)
    return await get_metrics_timeseries(session=db, days=valid_days, bucket=bucket, origin=origin)


@router.get("/metrics/hotspots")
async def get_metrics_hotspots_endpoint(
    days: Optional[int] = Query(None, description="Time range in days (1-90)"),
    origin: str = Query("all", description="all | live | simulated"),
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Admin-only incident heatmap grid (250m) aggregated via PostGIS ST_SnapToGrid."""
    valid_days = validate_days(days)
    return await get_metrics_hotspots(session=db, days=valid_days, origin=origin)


@router.get("/metrics/export.csv")
async def export_metrics_csv_endpoint(
    days: Optional[int] = Query(None, description="Time range in days (1-90)"),
    kind: str = Query("incidents", description="incidents | dispatches"),
    origin: str = Query("all", description="all | live | simulated"),
    current_admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Admin-only authenticated CSV stream export. Coordinates rounded to 3 decimals, no user IDs/emails."""
    valid_days = validate_days(days)
    csv_text = await export_metrics_csv(session=db, days=valid_days, kind=kind, origin=origin)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{kind}_export.csv"',
        },
    )


@router.get("/model-info")
async def get_model_info_endpoint(
    current_admin: User = Depends(require_role(UserRole.admin)),
) -> dict:
    """Admin-only endpoint reading ml/artifacts/metrics.json metadata and performance metrics."""
    return get_model_info()
