"""
Weather integration service using Open-Meteo public forecast API.
Normalizes meteorological data to match Bengaluru traffic dataset categories.
"""
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import httpx
import yaml

from app.core.cache import cache, make_weather_cache_key
from app.core.config import settings, BACKEND_DIR
from app.schemas.weather import WeatherResponse

logger = logging.getLogger("smartroute.weather")

MAPPING_FILE_PATH = Path(getattr(settings, "BACKEND_DIR", BACKEND_DIR)).parent / "ml" / "weather_mapping.yaml"

# Default fallback mapping in case YAML file cannot be loaded
DEFAULT_WMO_MAPPING = {
    0: "Clear",
    1: "Clear",
    2: "Overcast",
    3: "Overcast",
    45: "Fog",
    48: "Fog",
    51: "Rain",
    53: "Rain",
    55: "Rain",
    61: "Rain",
    63: "Rain",
    65: "Rain",
    80: "Rain",
    81: "Rain",
    82: "Rain",
    95: "Rain",
}


class WeatherService:
    """Service fetching and normalizing live Open-Meteo forecast data with in-memory TTL caching."""

    def __init__(self, mapping_path: Path = MAPPING_FILE_PATH) -> None:
        self.mapping_path = mapping_path
        self._wmo_mapping: Dict[int, str] = DEFAULT_WMO_MAPPING.copy()
        self._wind_threshold: float = 35.0
        self._default_condition: str = "Clear"
        self._load_mapping()
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop: Optional[Any] = None
        self._map_wmo_to_condition = self.map_weather_condition

    @property
    def client(self) -> httpx.AsyncClient:
        """Return or lazily create an AsyncClient bound to the current running event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if (
            self._client is None
            or self._client.is_closed
            or (self._client_loop is not None and (self._client_loop.is_closed() or (loop and self._client_loop is not loop)))
        ):
            self._client = httpx.AsyncClient(timeout=4.0)
            self._client_loop = loop
        return self._client

    @client.setter
    def client(self, value: httpx.AsyncClient) -> None:
        self._client = value
        try:
            self._client_loop = asyncio.get_running_loop()
        except RuntimeError:
            self._client_loop = None

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
        self._client_loop = None

    def _load_mapping(self) -> None:
        """Load weather condition categorization mapping from YAML."""
        if self.mapping_path.exists():
            try:
                content = self.mapping_path.read_text(encoding="utf-8")
                parsed = yaml.safe_load(content)
                if parsed and isinstance(parsed, dict):
                    raw_mapping = parsed.get("wmo_code_mapping", {})
                    self._wmo_mapping = {int(k): str(v) for k, v in raw_mapping.items()}
                    self._wind_threshold = float(parsed.get("wind_speed_threshold_kmh", 35.0))
                    self._default_condition = str(parsed.get("default_condition", "Clear"))
                    logger.info("Successfully loaded weather mapping from %s", self.mapping_path)
            except Exception as exc:
                logger.warning("Could not parse %s: %s. Using default mapping.", self.mapping_path, exc)

    def map_weather_condition(
        self,
        weather_code: int,
        wind_speed_kmh: float = 0.0,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Map WMO code and wind speed to dataset weather condition category."""
        wind = wind_speed_kmh
        if "wind_speed" in kwargs:
            wind = float(kwargs["wind_speed"])
        elif args:
            wind = float(args[0])
        base_condition = self._wmo_mapping.get(int(weather_code), self._default_condition)
        if wind >= self._wind_threshold and base_condition in ("Clear", "Overcast"):
            return "Windy"
        return base_condition

    async def get_weather(
        self,
        lat: Any,
        lng: Optional[float] = None,
        at_time: Optional[datetime] = None,
        when: Optional[datetime] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Optional[WeatherResponse]:
        """
        Fetch normalized weather conditions for coordinates and optional future departure time.
        Uses in-memory TTL cache with coordinates rounded to 2 decimals (~1.1 km).
        Returns None safely if Open-Meteo is unreachable without failing the caller.
        """
        # Support tuple/list input e.g. get_weather((12.97, 77.59), departure_time)
        if isinstance(lat, (tuple, list)) and len(lat) >= 2:
            query_lat = float(lat[0])
            query_lng = float(lat[1])
            target_time = lng if isinstance(lng, datetime) else (at_time or when or kwargs.get("time"))
        elif isinstance(lat, dict) and "lat" in lat and "lng" in lat:
            query_lat = float(lat["lat"])
            query_lng = float(lat["lng"])
            target_time = at_time or when or kwargs.get("time")
        else:
            query_lat = float(lat)
            query_lng = float(lng) if lng is not None else float(kwargs.get("longitude", kwargs.get("lng", 0.0)))
            target_time = at_time or when or kwargs.get("time")

        if args and target_time is None:
            for arg in args:
                if isinstance(arg, datetime):
                    target_time = arg
                    break

        time_key = target_time.strftime("%Y-%m-%d-%H") if target_time else None
        cache_key = make_weather_cache_key(query_lat, query_lng, time_key)

        cached: Optional[WeatherResponse] = cache.get(cache_key)
        if cached is not None:
            return cached

        # Round to 2 decimals for query
        q_lat = round(query_lat, 2)
        q_lng = round(query_lng, 2)

        params: Dict[str, Any] = {
            "latitude": q_lat,
            "longitude": q_lng,
            "current": "temperature_2m,precipitation,rain,weather_code,wind_speed_10m,visibility",
            "hourly": "temperature_2m,precipitation,rain,weather_code,wind_speed_10m,visibility",
            "timezone": "auto",
        }

        raw_data = await self._fetch_open_meteo(params)
        if not raw_data:
            return None

        try:
            weather_resp = self._parse_meteo_response(raw_data, target_time)
            cache.set(cache_key, weather_resp, ttl_seconds=settings.WEATHER_CACHE_TTL_S)
            return weather_resp
        except Exception as exc:
            logger.warning("Failed to parse Open-Meteo response: %s", exc)
            return None

    async def get_current_weather(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Optional[WeatherResponse]:
        """Backwards-compatibility alias for get_weather supporting all positional & keyword arguments."""
        return await self.get_weather(*args, **kwargs)

    async def _fetch_open_meteo(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call Open-Meteo API with timeout and 1 retry."""
        url = settings.OPEN_METEO_BASE_URL
        for attempt in range(2):
            try:
                resp = await self.client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning("Open-Meteo returned status %d on attempt %d", resp.status_code, attempt + 1)
            except Exception as exc:
                logger.warning("Open-Meteo connection attempt %d failed: %s", attempt + 1, exc)
        return None

    def _parse_meteo_response(
        self,
        data: Dict[str, Any],
        at_time: Optional[datetime] = None,
    ) -> WeatherResponse:
        """Extract and normalize meteorological variables."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # If at_time is specified and hourly data is present, match the closest hour
        if at_time and "hourly" in data and "time" in data["hourly"]:
            hourly = data["hourly"]
            times = hourly.get("time", [])
            target_str = at_time.strftime("%Y-%m-%dT%H:00")

            idx = 0
            if target_str in times:
                idx = times.index(target_str)
            else:
                # Find closest index
                try:
                    target_ts = at_time.timestamp()
                    idx = min(
                        range(len(times)),
                        key=lambda i: abs(datetime.fromisoformat(times[i]).timestamp() - target_ts),
                    )
                except Exception:
                    idx = 0

            temp = float(hourly.get("temperature_2m", [25.0])[idx])
            precip = float(hourly.get("precipitation", [0.0])[idx])
            code = int(hourly.get("weather_code", [0])[idx])
            wind = float(hourly.get("wind_speed_10m", [0.0])[idx])
            vis = float(hourly.get("visibility", [10000.0])[idx])
        else:
            # Current conditions
            current = data.get("current", {})
            temp = float(current.get("temperature_2m", 25.0))
            precip = float(current.get("precipitation", 0.0))
            code = int(current.get("weather_code", 0))
            wind = float(current.get("wind_speed_10m", 0.0))
            vis = float(current.get("visibility", 10000.0))

        condition = self.map_weather_condition(code, wind)

        return WeatherResponse(
            condition=condition,
            precipitation_mm=round(precip, 2),
            visibility_m=round(vis, 1),
            temperature_c=round(temp, 1),
            source="open-meteo",
            fetched_at=now_iso,
        )


weather_service = WeatherService()
get_current_weather = weather_service.get_current_weather
get_weather = weather_service.get_weather
