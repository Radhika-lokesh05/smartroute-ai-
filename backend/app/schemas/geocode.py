from typing import List, Optional
from pydantic import BaseModel, Field


class GeocodeResult(BaseModel):
    """Simplified, normalized geocode address item."""
    label: str = Field(..., description="Full descriptive address or location name")
    lat: float = Field(..., description="Latitude in WGS84")
    lng: float = Field(..., description="Longitude in WGS84")
    locality: Optional[str] = Field(None, description="City, town, or administrative locality")


class GeocodeResponse(BaseModel):
    """Normalized geocode response collection."""
    provider: str = Field("openrouteservice", description="Geocode provider service")
    warning: Optional[str] = None
    results: List[GeocodeResult]
