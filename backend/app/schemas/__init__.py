"""Pydantic schemas package."""
from app.schemas.health import HealthResponse
from app.schemas.user import UserRegister, UserLogin, UserResponse, TokenResponse
from app.schemas.ambulance import AmbulanceCreate, AmbulanceVerify, AmbulanceResponse
from app.schemas.routing import RouteResponse, RouteItem, RouteStep, GeoJSONLineString, RouteRequest, RouteTrafficSummary
from app.schemas.traffic import TrafficPredictRequest, TrafficPredictResponse
from app.schemas.geocode import GeocodeResponse, GeocodeResult
from app.schemas.incident import (
    IncidentCreate,
    IncidentVoteCreate,
    IncidentPublicResponse,
    IncidentListResponse,
)
from app.schemas.hospital import HospitalNearbyItem, HospitalNearbyResponse

__all__ = [
    "HealthResponse",
    "UserRegister",
    "UserLogin",
    "UserResponse",
    "TokenResponse",
    "AmbulanceCreate",
    "AmbulanceVerify",
    "AmbulanceResponse",
    "RouteResponse",
    "RouteItem",
    "RouteStep",
    "GeoJSONLineString",
    "RouteRequest",
    "RouteTrafficSummary",
    "TrafficPredictRequest",
    "TrafficPredictResponse",
    "GeocodeResponse",
    "GeocodeResult",
    "IncidentCreate",
    "IncidentVoteCreate",
    "IncidentPublicResponse",
    "IncidentListResponse",
    "HospitalNearbyItem",
    "HospitalNearbyResponse",
]
