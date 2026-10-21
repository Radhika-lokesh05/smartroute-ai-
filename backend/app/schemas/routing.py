from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class GeoJSONLineString(BaseModel):
    """GeoJSON LineString representation of route geometry."""
    type: str = "LineString"
    coordinates: List[List[float]] = Field(
        ...,
        description="Array of [longitude, latitude] coordinate pairs",
    )


class RouteStep(BaseModel):
    """Individual navigation turn-by-turn instruction."""
    instruction: str
    distance_m: float
    duration_s: float
    name: str = ""
    maneuver_type: str = Field("unknown", description="Maneuver identifier (e.g., turn-left, depart, arrive)")


class IncidentOnRoute(BaseModel):
    """Incident identified within buffer zone of a route."""
    id: str
    type: str = Field(..., description="accident | blockage | hazard")
    status: str = Field(..., description="pending | validated")
    lat: float
    lng: float
    distance_from_route_m: float


class RouteSummary(BaseModel):
    """Incident evaluation summary across all candidate routes."""
    incidents_considered: int = 0
    fastest_raw_route_index: int = 0
    recommended_route_index: int = 0
    rerouted: bool = False


from app.schemas.weather import WeatherResponse


class RouteTrafficSummary(BaseModel):
    """Traffic model metadata and environmental context."""
    model_config = ConfigDict(protected_namespaces=())

    model_version: str
    data_source: str = "kaggle-bangalore-city-traffic"
    data_granularity: str = "daily"
    time_of_day_modelled: bool = False
    model_available: bool = False
    weather: Optional[WeatherResponse] = None


class RouteItem(BaseModel):
    """Calculated route option with geometry, turn instructions, incident, and traffic impact metrics."""
    distance_m: float
    duration_s: float
    traffic_factor: float = 1.0
    predicted_duration_s: float = 0.0
    traffic_coverage: float = 0.0
    estimated_delay_s: float = 0.0
    adjusted_duration_s: float = 0.0
    incidents_on_route: List[IncidentOnRoute] = Field(default_factory=list)
    avoids_incidents: bool = False
    rank: int = 1
    reason: str = "No incidents on this route"
    geometry: GeoJSONLineString
    steps: List[RouteStep] = Field(default_factory=list)


class RouteResponse(BaseModel):
    """Response containing ranked routes, incident evaluation summary, and ML traffic metadata."""
    provider: str = Field("openrouteservice", description="Routing provider used")
    warning: Optional[str] = None
    summary: Optional[RouteSummary] = None
    traffic: Optional[RouteTrafficSummary] = None
    routes: List[RouteItem]


class RouteRequest(BaseModel):
    """Optional payload for requesting routes with parameters and avoid polygons."""
    from_lat: float = Field(..., ge=-90.0, le=90.0)
    from_lng: float = Field(..., ge=-180.0, le=180.0)
    to_lat: float = Field(..., ge=-90.0, le=90.0)
    to_lng: float = Field(..., ge=-180.0, le=180.0)
    avoid_polygons: Optional[Any] = Field(
        None,
        description="GeoJSON MultiPolygon or Polygon representing hazardous or congested zones to avoid",
    )
    use_incidents: bool = Field(True, description="Whether to evaluate and apply road incident penalties")
    departure_time: Optional[datetime] = Field(None, description="Optional ISO departure datetime (max 24h ahead)")
