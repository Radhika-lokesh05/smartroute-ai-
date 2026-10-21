import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas.incident import (
    IncidentCreate,
    IncidentListResponse,
    IncidentPublicResponse,
    IncidentVoteCreate,
)
from app.services.incident_service import (
    create_incident,
    extract_incident_lat_lng,
    get_incident_by_id,
    get_nearby_incidents,
    resolve_incident,
    serialize_incident_dict,
    serialize_incident_public,
    vote_incident,
)
from app.services.realtime import create_realtime_message, realtime_manager

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])


@router.post("", response_model=IncidentPublicResponse, status_code=status.HTTP_201_CREATED)
async def report_incident(
    payload: IncidentCreate,
    x_simulated: Optional[str] = Header(None, alias="X-Simulated"),
    is_simulated: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IncidentPublicResponse:
    """
    Report a new road incident or merge with existing active incident within deduplication radius.
    The database transaction is committed before broadcasting to the realtime WebSocket manager.
    Admin callers can specify X-Simulated: true or ?is_simulated=true for scenario runs.
    """
    sim_flag = False
    if current_user.role == UserRole.admin:
        if x_simulated == "true" or is_simulated is True:
            sim_flag = True

    incident, is_new, event_type = await create_incident(
        db=db,
        user=current_user,
        lat=payload.lat,
        lng=payload.lng,
        incident_type=payload.type,
        note=payload.note,
        is_simulated=sim_flag,
    )

    inc_lat, inc_lng = extract_incident_lat_lng(incident.location)

    # Realtime notification sent ONLY AFTER the DB transaction is committed
    realtime_data = serialize_incident_dict(incident, inc_lat, inc_lng)
    await realtime_manager.broadcast_to_area(
        inc_lat,
        inc_lng,
        create_realtime_message(event_type, realtime_data),
    )

    return serialize_incident_public(
        incident=incident,
        lat=inc_lat,
        lng=inc_lng,
        user_voted=True,
    )


@router.post("/{incident_id}/vote", response_model=IncidentPublicResponse)
async def submit_vote(
    incident_id: uuid.UUID,
    payload: IncidentVoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IncidentPublicResponse:
    """
    Submit a confirm or reject vote on an active incident within the allowed voting radius.
    """
    incident, event_type = await vote_incident(
        db=db,
        user=current_user,
        incident_id=incident_id,
        vote_type=payload.vote,
        voter_lat=payload.voter_lat,
        voter_lng=payload.voter_lng,
    )

    inc_lat, inc_lng = extract_incident_lat_lng(incident.location)

    # Realtime notification sent ONLY AFTER the DB transaction is committed
    realtime_data = serialize_incident_dict(incident, inc_lat, inc_lng)
    await realtime_manager.broadcast_to_area(
        inc_lat,
        inc_lng,
        create_realtime_message(event_type, realtime_data),
    )

    return serialize_incident_public(
        incident=incident,
        lat=inc_lat,
        lng=inc_lng,
        user_voted=True,
        user_vote=payload.vote,
    )


@router.post("/{incident_id}/resolve", response_model=IncidentPublicResponse)
async def resolve(
    incident_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IncidentPublicResponse:
    """
    Mark an incident as resolved.
    Allowed only for administrators, verified ambulance personnel, or the original reporter.
    """
    incident = await resolve_incident(
        db=db,
        user=current_user,
        incident_id=incident_id,
    )

    inc_lat, inc_lng = extract_incident_lat_lng(incident.location)

    # Realtime notification sent ONLY AFTER the DB transaction is committed
    realtime_data = serialize_incident_dict(incident, inc_lat, inc_lng)
    await realtime_manager.broadcast_to_area(
        inc_lat,
        inc_lng,
        create_realtime_message("incident.resolved", realtime_data),
    )

    return serialize_incident_public(
        incident=incident,
        lat=inc_lat,
        lng=inc_lng,
    )


@router.get("/nearby", response_model=IncidentListResponse)
async def list_nearby_incidents(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Center latitude"),
    lng: float = Query(..., ge=-180.0, le=180.0, description="Center longitude"),
    radius_m: float = Query(5000.0, ge=10.0, le=settings.MAX_SUBSCRIBE_RADIUS_M, description="Search radius in meters"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IncidentListResponse:
    """
    Query active (pending and validated) unexpired incidents within radius_m.
    Includes confirmations, rejections, status, seconds_remaining, distance_m, and user_voted status.
    Never exposes reporter emails or personal user information.
    """
    rows = await get_nearby_incidents(
        db=db,
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        user=current_user,
    )

    items = []
    for inc, dist, u_voted, u_vote in rows:
        inc_lat, inc_lng = extract_incident_lat_lng(inc.location)
        items.append(
            serialize_incident_public(
                incident=inc,
                lat=inc_lat,
                lng=inc_lng,
                user_voted=u_voted,
                user_vote=u_vote,
                distance_m=dist,
            )
        )

    return IncidentListResponse(total=len(items), incidents=items)


@router.get("/{incident_id}", response_model=IncidentPublicResponse)
async def get_incident(
    incident_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IncidentPublicResponse:
    """
    Retrieve single incident by ID.
    Never exposes reporter email or personal user information.
    """
    incident, user_voted, user_vote = await get_incident_by_id(
        db=db,
        incident_id=incident_id,
        user=current_user,
    )

    inc_lat, inc_lng = extract_incident_lat_lng(incident.location)
    return serialize_incident_public(
        incident=incident,
        lat=inc_lat,
        lng=inc_lng,
        user_voted=user_voted,
        user_vote=user_vote,
    )
