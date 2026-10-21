from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.weather import WeatherResponse
from app.services.weather_service import weather_service

router = APIRouter(prefix="/api/weather", tags=["Weather"])


@router.get("", response_model=WeatherResponse)
async def get_current_weather(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude in range [-90.0, 90.0]"),
    lng: float = Query(..., ge=-180.0, le=180.0, description="Longitude in range [-180.0, 180.0]"),
    current_user: User = Depends(get_current_user),
) -> WeatherResponse:
    """
    Get current weather for specified coordinates mapped to Bengaluru traffic dataset categories.
    Requires authenticated user.
    """
    weather = await weather_service.get_weather(lat=lat, lng=lng)
    if weather is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upstream weather service temporarily unavailable.",
        )
    return weather
