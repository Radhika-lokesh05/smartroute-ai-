"""
Incident lifecycle, spatial deduplication, voting, consensus, and resolution service.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Tuple
from fastapi import HTTPException, status
import re
import struct
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_GeogFromText
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.ambulance import Ambulance
from app.models.incident import Incident, IncidentStatus, IncidentType, IncidentVote, VoteType
from app.models.user import User, UserRole

logger = logging.getLogger("smartroute.incidents")


def _parse_wkb_point(raw_bytes: bytes) -> Tuple[float, float]:
    """Parse (lat, lng) from raw 2D WKB or PostGIS EWKB Point bytes using Python struct."""
    if len(raw_bytes) < 21:
        raise ValueError(f"WKB bytes too short for Point: {len(raw_bytes)}")
    byte_order = "<" if raw_bytes[0] == 1 else ">"
    geom_type = struct.unpack(f"{byte_order}I", raw_bytes[1:5])[0]

    # Check for EWKB SRID flag (0x20000000)
    has_srid = bool(geom_type & 0x20000000)
    offset = 9 if has_srid else 5

    if len(raw_bytes) < offset + 16:
        raise ValueError(f"WKB bytes too short for coordinates at offset {offset}")

    x, y = struct.unpack(f"{byte_order}dd", raw_bytes[offset : offset + 16])
    # OpenGIS / PostGIS standard: x is longitude, y is latitude
    return float(y), float(x)


def extract_incident_lat_lng(location: Any) -> Tuple[float, float]:
    """
    Extract (lat, lng) from GeoAlchemy2 Geography Point, WKBElement, WKTElement,
    hex WKB string, binary bytes, or WKT text using standard library without external dependencies.
    """
    # 1. Direct object with .x and .y attributes
    if hasattr(location, "x") and hasattr(location, "y"):
        return float(location.y), float(location.x)

    # 2. Extract raw data if location is a SpatialElement (WKBElement, WKTElement)
    data = getattr(location, "data", location)

    # Handle string data (could be hex-encoded WKB or WKT)
    if isinstance(data, str):
        trimmed = data.strip()
        # WKT text (e.g. "POINT(77.5946 12.9716)" or "SRID=4326;POINT(...)")
        if "POINT" in trimmed.upper():
            m = re.search(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", trimmed, re.IGNORECASE)
            if m:
                # WKT is POINT(lng lat) -> X is lng, Y is lat
                return float(m.group(2)), float(m.group(1))

        # Hex-encoded WKB string (e.g. 0101000000...)
        try:
            return _parse_wkb_point(bytes.fromhex(trimmed))
        except Exception:
            pass

    # Handle binary data (bytes, memoryview, bytearray)
    if isinstance(data, (bytes, memoryview, bytearray)):
        try:
            return _parse_wkb_point(bytes(data))
        except Exception:
            pass

    # 3. Fallback inspection on str(location)
    loc_str = str(location).strip()
    if "POINT" in loc_str.upper():
        m = re.search(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", loc_str, re.IGNORECASE)
        if m:
            return float(m.group(2)), float(m.group(1))

    try:
        return _parse_wkb_point(bytes.fromhex(loc_str))
    except Exception:
        pass

    raise ValueError(f"Unable to extract coordinates from location: {location}")


async def is_verified_ambulance_user(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Check if the user is a verified ambulance operator."""
    stmt = select(Ambulance.is_verified).where(Ambulance.user_id == user_id)
    res = await db.execute(stmt)
    return bool(res.scalar())


def get_user_vote_weight(user: User, is_verified_ambulance: bool) -> float:
    """Calculate the consensus weight carried by a user's confirmation."""
    if user.role == UserRole.admin:
        return settings.ADMIN_CONFIRM_WEIGHT
    if user.role == UserRole.ambulance and is_verified_ambulance:
        return settings.AMBULANCE_CONFIRM_WEIGHT
    return settings.CIVILIAN_CONFIRM_WEIGHT


async def check_report_rate_limit(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Enforce MAX_REPORTS_PER_10_MIN rate limit counted from DB created_at."""
    ten_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=10)
    stmt = (
        select(func.count(Incident.id), func.min(Incident.created_at))
        .where(Incident.reporter_id == user_id, Incident.created_at >= ten_mins_ago)
    )
    result = await db.execute(stmt)
    count, oldest_created = result.one()
    if count >= settings.MAX_REPORTS_PER_10_MIN:
        if oldest_created:
            if oldest_created.tzinfo is None:
                oldest_created = oldest_created.replace(tzinfo=timezone.utc)
            retry_after = max(1, int((oldest_created + timedelta(minutes=10) - datetime.now(timezone.utc)).total_seconds()))
        else:
            retry_after = 600
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: maximum {settings.MAX_REPORTS_PER_10_MIN} reports per 10 minutes.",
            headers={"Retry-After": str(retry_after)},
        )


async def check_vote_rate_limit(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Enforce MAX_VOTES_PER_HOUR rate limit counted from DB created_at."""
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    stmt = (
        select(func.count(IncidentVote.id), func.min(IncidentVote.created_at))
        .where(IncidentVote.user_id == user_id, IncidentVote.created_at >= one_hour_ago)
    )
    result = await db.execute(stmt)
    count, oldest_created = result.one()
    if count >= settings.MAX_VOTES_PER_HOUR:
        if oldest_created:
            if oldest_created.tzinfo is None:
                oldest_created = oldest_created.replace(tzinfo=timezone.utc)
            retry_after = max(1, int((oldest_created + timedelta(hours=1) - datetime.now(timezone.utc)).total_seconds()))
        else:
            retry_after = 3600
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: maximum {settings.MAX_VOTES_PER_HOUR} votes per hour.",
            headers={"Retry-After": str(retry_after)},
        )


async def create_incident(
    db: AsyncSession,
    user: User,
    lat: float,
    lng: float,
    incident_type: IncidentType,
    note: Optional[str] = None,
    is_simulated: Optional[bool] = False,
) -> Tuple[Incident, bool, str]:
    """
    Create a new incident or merge into existing active incident within INCIDENT_DEDUPE_RADIUS_M.
    Returns: (incident, is_new_incident, event_type)
    """
    await check_report_rate_limit(db, user.id)

    now = datetime.now(timezone.utc)
    point_wkt = f"SRID=4326;POINT({lng} {lat})"
    geog_point = ST_GeogFromText(point_wkt)

    # Spatial deduplication check:
    # If active (pending or validated, unexpired) incident of same type exists within INCIDENT_DEDUPE_RADIUS_M
    dedupe_stmt = (
        select(Incident)
        .where(
            Incident.status.in_([IncidentStatus.pending, IncidentStatus.validated]),
            Incident.expires_at > now,
            Incident.incident_type == incident_type,
            ST_DWithin(Incident.location, geog_point, settings.INCIDENT_DEDUPE_RADIUS_M),
        )
        .order_by(ST_Distance(Incident.location, geog_point))
        .limit(1)
        .with_for_update()
    )
    existing_incident = (await db.execute(dedupe_stmt)).scalar_one_or_none()

    wkt_location = WKTElement(f"POINT({lng} {lat})", srid=4326)

    if existing_incident is not None:
        # Check if the user is the original reporter or has already voted on this existing incident
        if existing_incident.reporter_id == user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already reported an active incident at this location.",
            )

        vote_stmt = select(IncidentVote).where(
            IncidentVote.incident_id == existing_incident.id,
            IncidentVote.user_id == user.id,
        )
        if (await db.execute(vote_stmt)).scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already voted on this incident.",
            )

        # Register report as a confirm vote on the existing incident
        is_verified_amb = await is_verified_ambulance_user(db, user.id)
        weight = get_user_vote_weight(user, is_verified_amb)

        confirm_vote = IncidentVote(
            incident_id=existing_incident.id,
            user_id=user.id,
            vote=VoteType.confirm,
            voter_location=wkt_location,
            created_at=now,
        )
        db.add(confirm_vote)

        existing_incident.confirmations += 1
        existing_incident.trust_score += weight

        event_type = "incident.updated"
        if (
            existing_incident.status == IncidentStatus.pending
            and (
                existing_incident.confirmations >= settings.VALIDATION_THRESHOLD
                or existing_incident.trust_score >= settings.VALIDATION_THRESHOLD
            )
        ):
            existing_incident.status = IncidentStatus.validated
            if existing_incident.validated_at is None:
                existing_incident.validated_at = now
            event_type = "incident.validated"

        await db.commit()
        await db.refresh(existing_incident)
        return existing_incident, False, event_type

    # Otherwise, create new incident
    is_verified_amb = await is_verified_ambulance_user(db, user.id)
    initial_weight = get_user_vote_weight(user, is_verified_amb)

    is_validated_initial = initial_weight >= settings.VALIDATION_THRESHOLD or settings.VALIDATION_THRESHOLD <= 1
    new_status = IncidentStatus.validated if is_validated_initial else IncidentStatus.pending
    validated_at_val = now if is_validated_initial else None

    new_incident = Incident(
        reporter_id=user.id,
        location=wkt_location,
        incident_type=incident_type,
        status=new_status,
        confirmations=1,  # Reporter's own report is the first confirmation
        rejections=0,
        trust_score=initial_weight,
        created_at=now,
        expires_at=now + timedelta(minutes=settings.INCIDENT_TTL_MINUTES),
        validated_at=validated_at_val,
        note=note,
        is_simulated=is_simulated,
    )
    db.add(new_incident)
    await db.flush()

    # Register the reporter's initial report as their vote in incident_votes
    reporter_vote = IncidentVote(
        incident_id=new_incident.id,
        user_id=user.id,
        vote=VoteType.confirm,
        voter_location=wkt_location,
        created_at=now,
    )
    db.add(reporter_vote)

    await db.commit()
    await db.refresh(new_incident)
    event_type = "incident.validated" if new_status == IncidentStatus.validated else "incident.created"
    return new_incident, True, event_type


async def vote_incident(
    db: AsyncSession,
    user: User,
    incident_id: uuid.UUID,
    vote_type: VoteType,
    voter_lat: float,
    voter_lng: float,
) -> Tuple[Incident, str]:
    """
    Vote on an incident within INCIDENT_VOTE_RADIUS_M under SELECT ... FOR UPDATE.
    Returns: (incident, event_type)
    """
    await check_vote_rate_limit(db, user.id)

    now = datetime.now(timezone.utc)
    voter_point = ST_GeogFromText(f"SRID=4326;POINT({voter_lng} {voter_lat})")

    # Select incident FOR UPDATE to prevent race conditions on confirmations/rejections
    stmt = select(Incident).where(Incident.id == incident_id).with_for_update()
    incident = (await db.execute(stmt)).scalar_one_or_none()

    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    # Only pending or validated incidents that have not expired can be voted on
    if incident.status not in (IncidentStatus.pending, IncidentStatus.validated) or incident.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incident is no longer active for voting.",
        )

    # Reporter cannot vote on their own incident again
    if incident.reporter_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reporter cannot vote on their own incident.",
        )

    # Check for duplicate vote (one vote per user per incident)
    existing_vote_stmt = select(IncidentVote).where(
        IncidentVote.incident_id == incident.id,
        IncidentVote.user_id == user.id,
    )
    if (await db.execute(existing_vote_stmt)).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User has already voted on this incident.",
        )

    # Distance check using PostGIS ST_DWithin
    distance_check_stmt = select(ST_DWithin(incident.location, voter_point, settings.INCIDENT_VOTE_RADIUS_M))
    is_within_radius = (await db.execute(distance_check_stmt)).scalar()

    if not is_within_radius:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Voter location exceeds the allowed voting radius of {int(settings.INCIDENT_VOTE_RADIUS_M)}m.",
        )

    # Create vote record
    vote_record = IncidentVote(
        incident_id=incident.id,
        user_id=user.id,
        vote=vote_type,
        voter_location=WKTElement(f"POINT({voter_lng} {voter_lat})", srid=4326),
        created_at=now,
    )
    db.add(vote_record)

    event_type = "incident.updated"
    is_verified_amb = await is_verified_ambulance_user(db, user.id)
    weight = get_user_vote_weight(user, is_verified_amb)

    if vote_type == VoteType.confirm:
        incident.confirmations += 1
        incident.trust_score += weight

        if (
            incident.status == IncidentStatus.pending
            and (
                incident.confirmations >= settings.VALIDATION_THRESHOLD
                or incident.trust_score >= settings.VALIDATION_THRESHOLD
            )
        ):
            incident.status = IncidentStatus.validated
            if incident.validated_at is None:
                incident.validated_at = now
            event_type = "incident.validated"

    elif vote_type == VoteType.reject:
        incident.rejections += 1

        # Incident is marked expired (reason: rejected) when rejections reach threshold and exceed confirmations
        if incident.rejections >= settings.REJECTION_THRESHOLD and incident.rejections > incident.confirmations:
            incident.status = IncidentStatus.expired
            incident.expiry_reason = "rejected"
            event_type = "incident.expired"

    await db.commit()
    await db.refresh(incident)
    return incident, event_type


async def resolve_incident(db: AsyncSession, user: User, incident_id: uuid.UUID) -> Incident:
    """
    Resolve an incident. Allowed for admin, a verified ambulance user, or original reporter.
    """
    now = datetime.now(timezone.utc)
    stmt = select(Incident).where(Incident.id == incident_id).with_for_update()
    incident = (await db.execute(stmt)).scalar_one_or_none()

    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    is_admin = user.role == UserRole.admin
    is_reporter = incident.reporter_id == user.id
    is_verified_ambulance = False
    if user.role == UserRole.ambulance:
        is_verified_ambulance = await is_verified_ambulance_user(db, user.id)

    if not (is_admin or is_reporter or is_verified_ambulance):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Resolution requires admin role, verified ambulance credentials, or original reporter identity.",
        )

    incident.status = IncidentStatus.resolved
    incident.resolved_at = now
    incident.resolved_by_id = user.id

    await db.commit()
    await db.refresh(incident)
    return incident


async def expire_old_incidents(db: AsyncSession) -> List[Incident]:
    """
    Marks incidents past expires_at as expired and returns them.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        select(Incident)
        .where(
            Incident.status.in_([IncidentStatus.pending, IncidentStatus.validated]),
            Incident.expires_at <= now,
        )
        .with_for_update()
    )
    incidents = (await db.execute(stmt)).scalars().all()
    for inc in incidents:
        inc.status = IncidentStatus.expired
        inc.expiry_reason = "timeout"

    if incidents:
        await db.commit()
        for inc in incidents:
            await db.refresh(inc)

    return list(incidents)


async def get_incident_by_id(
    db: AsyncSession,
    incident_id: uuid.UUID,
    user: Optional[User] = None,
) -> Tuple[Incident, bool, Optional[VoteType]]:
    """
    Retrieve single incident by ID along with current user's vote state.
    """
    stmt = select(Incident).where(Incident.id == incident_id)
    incident = (await db.execute(stmt)).scalar_one_or_none()
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    user_voted = False
    user_vote = None
    if user is not None:
        vote_stmt = select(IncidentVote.vote).where(
            IncidentVote.incident_id == incident.id,
            IncidentVote.user_id == user.id,
        )
        vote_res = await db.execute(vote_stmt)
        val = vote_res.scalar_one_or_none()
        if val is not None:
            user_voted = True
            user_vote = val

    return incident, user_voted, user_vote


async def get_nearby_incidents(
    db: AsyncSession,
    lat: float,
    lng: float,
    radius_m: float,
    user: User,
) -> List[Tuple[Incident, float, bool, Optional[VoteType]]]:
    """
    Retrieve active (pending or validated) unexpired incidents within radius_m.
    Returns list of (incident, distance_m, user_voted, user_vote).
    """
    now = datetime.now(timezone.utc)
    clamped_radius = max(100.0, min(float(radius_m), settings.MAX_SUBSCRIBE_RADIUS_M))
    user_point = ST_GeogFromText(f"SRID=4326;POINT({lng} {lat})")
    distance_col = ST_Distance(Incident.location, user_point).label("distance_m")

    stmt = (
        select(Incident, distance_col)
        .where(
            Incident.status.in_([IncidentStatus.pending, IncidentStatus.validated]),
            Incident.expires_at > now,
            ST_DWithin(Incident.location, user_point, clamped_radius),
        )
        .order_by(distance_col)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    # Batch load user votes for these incidents
    incident_ids = [row[0].id for row in rows]
    votes_stmt = select(IncidentVote.incident_id, IncidentVote.vote).where(
        IncidentVote.incident_id.in_(incident_ids),
        IncidentVote.user_id == user.id,
    )
    votes_map = dict((await db.execute(votes_stmt)).all())

    results = []
    for inc, dist in rows:
        u_vote = votes_map.get(inc.id)
        u_voted = u_vote is not None
        results.append((inc, float(dist), u_voted, u_vote))

    return results


def serialize_incident_public(
    incident: Incident,
    lat: float,
    lng: float,
    user_voted: bool = False,
    user_vote: Optional[VoteType] = None,
    distance_m: Optional[float] = None,
):
    """Convert Incident model to IncidentPublicResponse schema."""
    from app.schemas.incident import IncidentPublicResponse

    now = datetime.now(timezone.utc)
    seconds_remaining = max(0, int((incident.expires_at - now).total_seconds()))
    return IncidentPublicResponse(
        id=incident.id,
        incident_type=incident.incident_type,
        status=incident.status,
        lat=lat,
        lng=lng,
        confirmations=incident.confirmations,
        rejections=incident.rejections,
        trust_score=incident.trust_score,
        created_at=incident.created_at,
        expires_at=incident.expires_at,
        validated_at=incident.validated_at,
        resolved_at=incident.resolved_at,
        seconds_remaining=seconds_remaining,
        note=incident.note,
        user_voted=user_voted,
        user_vote=user_vote,
        distance_m=distance_m,
    )


def serialize_incident_dict(incident: Incident, lat: float, lng: float) -> dict:
    """Format sanitized public incident dictionary for WebSocket events."""
    now = datetime.now(timezone.utc)
    seconds_remaining = max(0, int((incident.expires_at - now).total_seconds()))
    return {
        "id": str(incident.id),
        "incident_type": incident.incident_type.value,
        "status": incident.status.value,
        "lat": lat,
        "lng": lng,
        "confirmations": incident.confirmations,
        "rejections": incident.rejections,
        "trust_score": round(incident.trust_score, 2),
        "created_at": incident.created_at.isoformat(),
        "expires_at": incident.expires_at.isoformat(),
        "validated_at": incident.validated_at.isoformat() if incident.validated_at else None,
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
        "seconds_remaining": seconds_remaining,
        "note": incident.note,
    }

