from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.rate_limit import rate_limited_user
from app.models.user import User
from app.services.geocode_service import geocode_service
from app.schemas.geocode import GeocodeResponse
from app.services.ors_client import (
    ORSKeyError,
    ORSNoRouteError,
    ORSRateLimitError,
    ORSProviderError,
    ORSNetworkError,
)

router = APIRouter(prefix="/api/geocode", tags=["Geocoding"])


def handle_ors_exception(exc: Exception) -> None:
    """Safely map ORS exceptions to clean HTTP exceptions without leaking keys or raw errors."""
    if isinstance(exc, ORSKeyError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Geocoding service temporarily unavailable due to upstream configuration.",
        )
    if isinstance(exc, ORSNoRouteError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching location found.",
        )
    if isinstance(exc, ORSRateLimitError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Upstream geocoding quota reached. Please try again shortly.",
        )
    if isinstance(exc, (ORSProviderError, ORSNetworkError)):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Geocoding service provider is currently unreachable.",
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred during geocoding.",
    )


@router.get("/autocomplete", response_model=GeocodeResponse)
async def autocomplete(
    q: str = Query(..., min_length=3, max_length=200, description="Address search query (3-200 characters)"),
    focus_lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Optional focus latitude"),
    focus_lng: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Optional focus longitude"),
    current_user: User = Depends(rate_limited_user),
) -> GeocodeResponse:
    """
    Search-as-you-type autocomplete restricted to India.
    Requires authenticated user and enforces rate limiting.
    """
    focus_point = (focus_lat, focus_lng) if focus_lat is not None and focus_lng is not None else None
    try:
        return await geocode_service.autocomplete(q, focus_point=focus_point)
    except Exception as exc:
        handle_ors_exception(exc)


@router.get("/search", response_model=GeocodeResponse)
async def search(
    q: str = Query(..., min_length=3, max_length=200, description="Full address query (3-200 characters)"),
    current_user: User = Depends(rate_limited_user),
) -> GeocodeResponse:
    """
    Forward geocode search query restricted to India.
    Requires authenticated user and enforces rate limiting.
    """
    try:
        return await geocode_service.search(q)
    except Exception as exc:
        handle_ors_exception(exc)


@router.get("/reverse", response_model=GeocodeResponse)
async def reverse(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude in range [-90.0, 90.0]"),
    lng: float = Query(..., ge=-180.0, le=180.0, description="Longitude in range [-180.0, 180.0]"),
    current_user: User = Depends(rate_limited_user),
) -> GeocodeResponse:
    """
    Reverse geocoding (coordinates to address) restricted to India.
    Requires authenticated user and enforces rate limiting.
    """
    try:
        return await geocode_service.reverse(lat, lng)
    except Exception as exc:
        handle_ors_exception(exc)
