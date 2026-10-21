"""Pydantic schemas for traffic prediction."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class WeatherUsed(BaseModel):
    condition: str = "Clear"
    temperature_c: float = 25.0


class TrafficPredictRequest(BaseModel):
    zone: Optional[str] = Field(None, description="Known traffic zone name (e.g. Indiranagar, Whitefield)")
    lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Latitude")
    lng: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Longitude")
    departure_time: Optional[datetime] = Field(None, description="Optional ISO departure datetime")

    @model_validator(mode="before")
    @classmethod
    def check_zone_or_coords(cls, values):
        if isinstance(values, dict):
            zone = values.get("zone")
            lat = values.get("lat")
            lng = values.get("lng")
            if not zone and (lat is None or lng is None):
                raise ValueError("Must provide either 'zone' or both 'lat' and 'lng'.")
        return values


class TrafficPredictResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    zone: Optional[str]
    traffic_factor: float
    predicted_category: str = Field(..., description="low | moderate | heavy | severe")
    weather_used: WeatherUsed
    departure_time: str
    model_version: str
    model_available: bool
