"""Tests for weather service, traffic ML integration, route calculation, and prediction API."""
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache
from app.core.rate_limit import rate_limiter
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole
from app.schemas.routing import GeoJSONLineString, RouteItem, RouteResponse, RouteStep
from app.services.ors_client import ors_client
from app.services.routing_service import RoutingService, routing_service
from app.services.traffic_model import TrafficModelService, traffic_model_service
from app.services.weather_service import WeatherService, weather_service


@pytest.fixture(autouse=True)
def reset_cache():
    cache.clear()
    rate_limiter.clear()
    yield
    cache.clear()
    rate_limiter.clear()


@pytest.fixture
async def auth_headers(db_session: AsyncSession) -> Dict[str, str]:
    user = User(
        id=uuid.uuid4(),
        name="Traffic Test User",
        email=f"traffic_user_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("password123"),
        role=UserRole.civilian,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(subject=str(user.id), role="civilian")
    return {"Authorization": f"Bearer {token}"}


# -------------------------------------------------------------------------
# 1. Weather Client & Open-Meteo Integration
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weather_service_success():
    """Mocked Open-Meteo response returns normalized WeatherResponse."""
    svc = WeatherService()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "current": {
            "weather_code": 61,  # Rain
            "precipitation": 2.5,
            "visibility": 5000.0,
            "temperature_2m": 22.0,
            "wind_speed_10m": 12.0,
        }
    }

    with patch.object(svc.client, "get", AsyncMock(return_value=mock_response)):
        res = await svc.get_weather(12.9716, 77.5946)
        assert res is not None
        assert res.condition == "Rain"
        assert res.precipitation_mm == 2.5
        assert res.visibility_m == 5000.0
        assert res.temperature_c == 22.0
        assert res.source == "open-meteo"


@pytest.mark.asyncio
async def test_weather_service_timeout_fallback_to_none():
    """Open-Meteo timeout safely falls back to None without crashing."""
    svc = WeatherService()
    with patch.object(svc.client, "get", AsyncMock(side_effect=httpx.TimeoutException("Timeout"))):
        res = await svc.get_weather(12.9716, 77.5946)
        assert res is None


@pytest.mark.asyncio
async def test_weather_service_http_error_fallback_to_none():
    """Open-Meteo 500 or 400 safely falls back to None."""
    svc = WeatherService()
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=mock_response)

    with patch.object(svc.client, "get", AsyncMock(return_value=mock_response)):
        res = await svc.get_weather(12.9716, 77.5946)
        assert res is None


@pytest.mark.asyncio
async def test_weather_service_get_current_weather_alias():
    """Verify get_current_weather forwards accurately with or without at_time."""
    from app.services.weather_service import get_current_weather
    svc = WeatherService()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "current": {
            "weather_code": 0,
            "precipitation": 0.0,
            "visibility": 10000.0,
            "temperature_2m": 25.0,
            "wind_speed_10m": 5.0,
        }
    }
    with patch.object(svc.client, "get", AsyncMock(return_value=mock_resp)):
        res1 = await svc.get_current_weather(12.9716, 77.5946)
        assert res1 is not None
        assert res1.condition == "Clear"

        res2 = await svc.get_current_weather(12.9716, 77.5946, at_time=datetime.now(timezone.utc))
        assert res2 is not None

        res3 = await svc.get_current_weather((12.9716, 77.5946))
        assert res3 is not None


# -------------------------------------------------------------------------
# 2. Weather Mapping & Wind Threshold
# -------------------------------------------------------------------------

def test_weather_mapping_wmo_codes():
    """Verify standard WMO codes map correctly to dataset weather categories."""
    svc = WeatherService()
    # 0, 1 -> Clear
    assert svc._map_wmo_to_condition(0, wind_speed_kmh=10.0) == "Clear"
    assert svc._map_wmo_to_condition(1, wind_speed_kmh=10.0) == "Clear"
    # 2, 3 -> Overcast
    assert svc._map_wmo_to_condition(2, wind_speed_kmh=10.0) == "Overcast"
    assert svc._map_wmo_to_condition(3, wind_speed_kmh=10.0) == "Overcast"
    # 45, 48 -> Fog
    assert svc._map_wmo_to_condition(45, wind_speed_kmh=10.0) == "Fog"
    assert svc._map_wmo_to_condition(48, wind_speed_kmh=10.0) == "Fog"
    # 61, 80, 95 -> Rain
    assert svc._map_wmo_to_condition(61, wind_speed_kmh=10.0) == "Rain"
    assert svc._map_wmo_to_condition(80, wind_speed_kmh=10.0) == "Rain"
    assert svc._map_wmo_to_condition(95, wind_speed_kmh=10.0) == "Rain"


def test_weather_mapping_wind_threshold():
    """Wind speed >= 35 km/h overrides WMO code to 'Windy'."""
    svc = WeatherService()
    # Code 0 (normally Clear) becomes Windy if wind is 36 km/h
    assert svc._map_wmo_to_condition(0, wind_speed_kmh=36.0) == "Windy"
    # Code 3 (normally Overcast) becomes Windy if wind is 35.0 km/h
    assert svc._map_wmo_to_condition(3, wind_speed_kmh=35.0) == "Windy"
    # Less than 35 remains standard mapping
    assert svc._map_wmo_to_condition(0, wind_speed_kmh=34.9) == "Clear"


# -------------------------------------------------------------------------
# 3. Weather Caching (TTL)
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weather_caching_within_ttl():
    """Subsequent call for same coordinates within 900s hits cache and does not call Open-Meteo."""
    svc = WeatherService()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "current": {
            "weather_code": 0,
            "precipitation": 0.0,
            "visibility": 10000.0,
            "temperature_2m": 26.5,
            "wind_speed_10m": 8.0,
        }
    }

    mock_get = AsyncMock(return_value=mock_response)
    with patch.object(svc.client, "get", mock_get):
        res1 = await svc.get_weather(12.9716, 77.5946)
        assert res1 is not None
        assert mock_get.call_count == 1

        # Second call with same coordinates
        res2 = await svc.get_weather(12.9716, 77.5946)
        assert res2 is not None
        assert res2.temperature_c == 26.5
        # Call count should still be 1 (served from in-memory cache)
        assert mock_get.call_count == 1


# -------------------------------------------------------------------------
# 4. Missing Model Fallback
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_model_fallback(auth_client: AsyncClient, auth_headers: Dict[str, str]):
    """If model is missing or disabled, routing and traffic service safely default to 1.0 without crashing."""
    mock_svc = TrafficModelService()
    mock_svc.model = None
    mock_svc.model_available = False

    factor = mock_svc.predict_factor("Indiranagar", datetime.now(timezone.utc), "Clear")
    assert factor == 1.0

    route_coords = [[77.5946, 12.9716], [77.6000, 12.9800]]
    calc_factor, coverage = mock_svc.calculate_route_traffic(route_coords, datetime.now(timezone.utc), "Clear")
    assert calc_factor == 1.0


# -------------------------------------------------------------------------
# 5. Length-Weighted Traffic Calculation
# -------------------------------------------------------------------------

def test_length_weighted_traffic_calculation():
    """Unit test: 3-segment route crossing known and unknown zones."""
    svc = TrafficModelService()
    # Configure 2 mock zones
    svc.zones = [
        {"name": "ZoneA", "lat": 12.90, "lng": 77.50, "radius_km": 5.0},
        {"name": "ZoneB", "lat": 12.95, "lng": 77.55, "radius_km": 5.0},
    ]
    svc.model_available = True
    mock_model = MagicMock()
    # Return 1.2 for ZoneA, 1.4 for ZoneB
    def mock_predict(df):
        area = df["area"].iloc[0]
        if area == "ZoneA":
            return [1.2]
        if area == "ZoneB":
            return [1.4]
        return [1.0]

    mock_model.predict = mock_predict
    svc.model = mock_model

    # Synthetic coordinates:
    # Segment 1: around ZoneA center (12.90, 77.50)
    # Segment 2: around ZoneB center (12.95, 77.55)
    # Segment 3: far away in unknown territory (13.50, 78.50)
    coords = [
        [77.50, 12.90],
        [77.501, 12.901],
        [77.55, 12.95],
        [78.50, 13.50],
    ]

    factor, coverage = svc.calculate_route_traffic(coords, datetime.now(timezone.utc), "Clear")
    assert factor >= 1.0
    assert 0.0 <= coverage <= 1.0


# -------------------------------------------------------------------------
# 6. No Double-Counting Delay Formula
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_double_counting_duration_calculation():
    """Verify adjusted_duration_s = predicted_duration_s + estimated_delay_s (not (duration + delay) * factor)."""
    raw_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[77.60, 12.90], [77.61, 12.91]],
        },
        "properties": {
            "summary": {"duration": 600.0, "distance": 5000.0},
            "segments": [],
        },
    }
    raw_ors_data = {"type": "FeatureCollection", "features": [raw_feature]}

    service = RoutingService()
    service.get_raw_routes = AsyncMock(return_value=service._parse_ors_response(raw_ors_data))

    with patch.object(traffic_model_service, "calculate_route_traffic", return_value=(1.25, 0.8)):
        with patch.object(weather_service, "get_weather", AsyncMock(return_value=None)):
            res = await service.get_routes(
                origin=(12.90, 77.60),
                destination=(12.91, 77.61),
                use_incidents=False,
            )

            r = res.routes[0]
            # duration_s = 600.0, traffic_factor = 1.25
            assert r.duration_s == 600.0
            assert r.traffic_factor == 1.25
            assert r.predicted_duration_s == 750.0  # 600 * 1.25
            assert r.estimated_delay_s == 0.0
            assert r.adjusted_duration_s == 750.0

            # Route reason mentions ~25% slower
            assert "25% slower" in r.reason


# -------------------------------------------------------------------------
# 7. GET /api/routes departure_time Validation
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_departure_time_validation_future_rejected(auth_client: AsyncClient, auth_headers: Dict[str, str]):
    """departure_time > 24 hours in the future returns HTTP 422."""
    far_future = (datetime.now(timezone.utc) + timedelta(hours=25)).isoformat()
    resp = await auth_client.get(
        f"/api/routes?from_lat=12.97&from_lng=77.59&to_lat=12.98&to_lng=77.60&departure_time={far_future}",
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "departure_time cannot be more than 24 hours in the future" in resp.text


@pytest.mark.asyncio
async def test_departure_time_validation_past_rejected(auth_client: AsyncClient, auth_headers: Dict[str, str]):
    """departure_time > 5 minutes in the past returns HTTP 422."""
    past = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    resp = await auth_client.get(
        f"/api/routes?from_lat=12.97&from_lng=77.59&to_lat=12.98&to_lng=77.60&departure_time={past}",
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "departure_time cannot be in the past" in resp.text


@pytest.mark.asyncio
async def test_departure_time_validation_valid_future_accepted(auth_client: AsyncClient, auth_headers: Dict[str, str]):
    """departure_time 2 hours in future is accepted."""
    valid_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    raw_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[77.59, 12.97], [77.60, 12.98]],
        },
        "properties": {
            "summary": {"duration": 500.0, "distance": 4000.0},
            "segments": [],
        },
    }
    with patch.object(ors_client, "request", AsyncMock(return_value={"features": [raw_feature]})):
        with patch.object(weather_service, "get_weather", AsyncMock(return_value=None)):
            resp = await auth_client.get(
                f"/api/routes?from_lat=12.97&from_lng=77.59&to_lat=12.98&to_lng=77.60&departure_time={valid_time}",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "routes" in data
            assert len(data["routes"]) == 1
            assert data["traffic"] is not None
            assert data["traffic"]["time_of_day_modelled"] is False
            assert data["traffic"]["data_granularity"] == "daily"


# -------------------------------------------------------------------------
# 8. POST /api/traffic/predict
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_traffic_predict_endpoint_by_zone(auth_client: AsyncClient, auth_headers: Dict[str, str]):
    """POST /api/traffic/predict with zone returns factor, category, and metadata."""
    payload = {"zone": "Indiranagar"}
    resp = await auth_client.post("/api/traffic/predict", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["zone"] == "Indiranagar"
    assert data["traffic_factor"] >= 1.0
    assert data["predicted_category"] in ["low", "moderate", "heavy", "severe"]
    assert "weather_used" in data
    assert "departure_time" in data


@pytest.mark.asyncio
async def test_traffic_predict_endpoint_by_coordinates(auth_client: AsyncClient, auth_headers: Dict[str, str]):
    """POST /api/traffic/predict with coordinates resolves zone or falls back safely."""
    payload = {"lat": 12.9784, "lng": 77.6408}
    resp = await auth_client.post("/api/traffic/predict", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["traffic_factor"] >= 1.0
    assert data["predicted_category"] in ["low", "moderate", "heavy", "severe"]


@pytest.mark.asyncio
async def test_traffic_predict_endpoint_invalid_payload(auth_client: AsyncClient, auth_headers: Dict[str, str]):
    """POST /api/traffic/predict without zone or lat/lng fails with HTTP 422."""
    payload = {}
    resp = await auth_client.post("/api/traffic/predict", json=payload, headers=auth_headers)
    assert resp.status_code == 422
