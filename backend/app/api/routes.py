import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import rate_limited_user
from app.models.user import User
from app.services.routing_service import routing_service
from app.schemas.routing import RouteResponse, RouteRequest
from app.services.ors_client import (
    ORSKeyError,
    ORSNoRouteError,
    ORSRateLimitError,
    ORSProviderError,
    ORSNetworkError,
)

router = APIRouter(prefix="/api/routes", tags=["Routing"])


def validate_departure_time(departure_time: Optional[Union[datetime, str]]) -> datetime:
    """Validate departure_time: default to now, reject if > 24h future or > 5m past."""
    now = datetime.now(timezone.utc)
    if departure_time is None:
        return now

    if isinstance(departure_time, str):
        cleaned = departure_time.strip().replace(" ", "+")
        try:
            dt = datetime.fromisoformat(cleaned)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="departure_time must be a valid ISO 8601 string",
            )
    else:
        dt = departure_time

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    if dt > now + timedelta(hours=24):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="departure_time cannot be more than 24 hours in the future",
        )
    if dt < now - timedelta(minutes=5):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="departure_time cannot be in the past",
        )
    return dt


def handle_routing_exception(exc: Exception) -> None:
    """Safely map routing exceptions to HTTP status codes without leaking secrets."""
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, ORSKeyError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Routing service temporarily unavailable due to upstream configuration.",
        )
    if isinstance(exc, ORSNoRouteError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No viable route found between the specified coordinates.",
        )
    if isinstance(exc, ORSRateLimitError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Upstream routing quota reached. Please try again shortly.",
        )
    if isinstance(exc, (ORSProviderError, ORSNetworkError)):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Routing service provider is currently unreachable.",
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred during route calculation.",
    )


@router.get("", response_model=RouteResponse)
async def get_routes_get(
    from_lat: float = Query(..., ge=-90.0, le=90.0, description="Origin latitude in range [-90.0, 90.0]"),
    from_lng: float = Query(..., ge=-180.0, le=180.0, description="Origin longitude in range [-180.0, 180.0]"),
    to_lat: float = Query(..., ge=-90.0, le=90.0, description="Destination latitude in range [-90.0, 90.0]"),
    to_lng: float = Query(..., ge=-180.0, le=180.0, description="Destination longitude in range [-180.0, 180.0]"),
    departure_time: Optional[str] = Query(None, description="Optional ISO 8601 departure datetime (max 24h ahead)"),
    avoid_polygons_json: Optional[str] = Query(None, description="Optional GeoJSON MultiPolygon formatted as JSON string"),
    use_incidents: bool = Query(True, description="Whether to evaluate road incidents and apply delay penalties"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(rate_limited_user),
) -> RouteResponse:
    """
    Calculate up to 4 driving routes between origin and destination with incident-aware ranking.
    Requires authenticated user and enforces rate limiting.
    """
    valid_departure = validate_departure_time(departure_time)

    avoid_polygons = None
    if avoid_polygons_json:
        try:
            avoid_polygons = json.loads(avoid_polygons_json)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid avoid_polygons GeoJSON format",
            )

    try:
        return await routing_service.get_routes(
            origin=(from_lat, from_lng),
            destination=(to_lat, to_lng),
            avoid_polygons=avoid_polygons,
            use_incidents=use_incidents,
            db=db,
            departure_time=valid_departure,
        )
    except Exception as exc:
        handle_routing_exception(exc)


@router.post("", response_model=RouteResponse)
async def get_routes_post(
    request: RouteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(rate_limited_user),
) -> RouteResponse:
    """
    POST route calculation supporting structured GeoJSON avoid_polygons and use_incidents flag.
    Requires authenticated user and enforces rate limiting.
    """
    valid_departure = validate_departure_time(request.departure_time)
    try:
        return await routing_service.get_routes(
            origin=(request.from_lat, request.from_lng),
            destination=(request.to_lat, request.to_lng),
            avoid_polygons=request.avoid_polygons,
            use_incidents=request.use_incidents,
            db=db,
            departure_time=valid_departure,
        )
    except Exception as exc:
        handle_routing_exception(exc)

