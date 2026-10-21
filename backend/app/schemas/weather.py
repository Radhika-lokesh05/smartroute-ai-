from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class WeatherResponse(BaseModel):
    """Normalized weather payload mapped to traffic dataset categories."""
    condition: str = Field(..., description="Dataset weather category: Clear | Overcast | Fog | Rain | Windy")
    precipitation_mm: float = Field(0.0, description="Precipitation amount in mm")
    visibility_m: float = Field(10000.0, description="Visibility in meters")
    temperature_c: float = Field(25.0, description="Ambient temperature in degrees Celsius")
    source: str = Field("open-meteo", description="Weather data provider")
    fetched_at: str = Field(..., description="ISO 8601 timestamp of data retrieval")
