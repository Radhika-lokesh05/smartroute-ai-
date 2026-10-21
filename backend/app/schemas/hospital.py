"""Pydantic schemas for hospital ranking and emergency telemetry."""
import uuid
from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.routing import GeoJSONLineString


class HospitalNearbyItem(BaseModel):
    id: uuid.UUID
    name: str
    lat: float
    lng: float
    phone: Optional[str] = None
    address: Optional[str] = None
    eta_s: float = Field(..., description="Estimated travel time in seconds including traffic and incident delay")
    distance_m: float = Field(..., description="Route distance in meters")
    matches_type: bool = Field(True, description="Whether hospital specializes in requested emergency type")
    simulated_beds: int = Field(..., description="Simulated emergency bed capacity")
    beds_simulated: bool = Field(True, description="Always true, bed numbers are simulated for demonstration")
    eta_estimated: bool = Field(False, description="True if real routing failed and straight-line approximation was used")
    route_geometry: Optional[GeoJSONLineString] = Field(None, description="GeoJSON geometry provided for the best hospital only")


class HospitalNearbyResponse(BaseModel):
    emergency_number: str = Field("112", description="Primary national emergency helpline")
    disclaimer: str = Field(
        "Suggestions only, not medical advice. Bed numbers are simulated.",
        description="Medical and capacity disclosure notice",
    )
    hospitals: List[HospitalNearbyItem]
