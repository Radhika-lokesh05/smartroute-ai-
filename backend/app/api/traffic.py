"""Traffic prediction API endpoints."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.traffic import (
    TrafficPredictRequest,
    TrafficPredictResponse,
    WeatherUsed,
)
from app.services.traffic_model import traffic_model_service
from app.services.weather_service import weather_service

router = APIRouter(prefix="/api/traffic", tags=["Traffic"])


def get_traffic_category(factor: float) -> str:
    """Categorize congestion factor: low (<1.15), moderate (1.15-1.35), heavy (1.35-1.55), severe (>1.55)."""
    if factor < 1.15:
        return "low"
    elif factor < 1.35:
        return "moderate"
    elif factor <= 1.55:
        return "heavy"
    return "severe"


@router.post("/predict", response_model=TrafficPredictResponse)
async def predict_traffic(
    request: TrafficPredictRequest,
    current_user: User = Depends(get_current_user),
) -> TrafficPredictResponse:
    """
    Predict traffic congestion factor and category for a given zone or coordinates.
    Requires authenticated user.
    """
    dep_time = request.departure_time or datetime.now(timezone.utc)
    if dep_time.tzinfo is None:
        dep_time = dep_time.replace(tzinfo=timezone.utc)

    target_zone: Optional[str] = None
    query_lat: Optional[float] = request.lat
    query_lng: Optional[float] = request.lng

    if request.zone:
        # Match zone case-insensitively against known zones
        zone_clean = request.zone.strip().lower()
        matched = next((z for z in traffic_model_service.zones if z["name"].lower() == zone_clean), None)
        if matched:
            target_zone = matched["name"]
            if query_lat is None or query_lng is None:
                query_lat, query_lng = matched["lat"], matched["lng"]
        else:
            target_zone = request.zone.strip()

    if target_zone is None and query_lat is not None and query_lng is not None:
        found_zone, _ = traffic_model_service.get_zone_for_point(query_lat, query_lng)
        target_zone = found_zone if found_zone != "unknown" else None

    # Retrieve weather at location if coordinates are available
    weather_cond = "Clear"
    temp_c = 25.0
    if query_lat is not None and query_lng is not None:
        weather = await weather_service.get_weather(query_lat, query_lng, at_time=dep_time)
        if weather:
            weather_cond = weather.condition
            temp_c = weather.temperature_c

    effective_zone = target_zone if target_zone else "unknown"
    factor = traffic_model_service.predict_factor(effective_zone, when=dep_time, weather=weather_cond)
    category = get_traffic_category(factor)

    return TrafficPredictResponse(
        zone=target_zone,
        traffic_factor=round(factor, 3),
        predicted_category=category,
        weather_used=WeatherUsed(condition=weather_cond, temperature_c=temp_c),
        departure_time=dep_time.isoformat(),
        model_version=traffic_model_service.model_version,
        model_available=traffic_model_service.model_available,
    )
