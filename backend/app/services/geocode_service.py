import logging
from typing import Dict, List, Optional, Tuple
from app.core.config import settings
from app.core.cache import (
    cache,
    make_geocode_cache_key,
    make_reverse_cache_key,
)
from app.services.ors_client import ors_client
from app.schemas.geocode import GeocodeResult, GeocodeResponse

logger = logging.getLogger(__name__)


class GeocodeService:
    """Geocoding service using Pelias on HeiGIT/OpenRouteService restricted to India."""

    def __init__(self, client=ors_client) -> None:
        self.client = client

    async def autocomplete(
        self,
        text: str,
        focus_point: Optional[Tuple[float, float]] = None,
    ) -> GeocodeResponse:
        """Typeahead address autocomplete restricted to India with optional focus point (lat, lng)."""
        focus_lat = focus_point[0] if focus_point else None
        focus_lng = focus_point[1] if focus_point else None

        # Check Cache
        cache_key = make_geocode_cache_key("auto", text, focus_lat, focus_lng)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        params: Dict[str, str] = {
            "text": text.strip(),
            "boundary.country": "IN",
        }
        if focus_lat is not None and focus_lng is not None:
            params["focus.point.lat"] = str(focus_lat)
            params["focus.point.lon"] = str(focus_lng)

        raw = await self.client.request(
            method="GET",
            path_or_url=settings.ORS_GEOCODE_AUTOCOMPLETE_PATH,
            params=params,
        )
        results = self._parse_pelias_features(raw)
        response = GeocodeResponse(provider="openrouteservice", results=results)

        cache.set(cache_key, response, ttl_seconds=settings.CACHE_TTL_SECONDS)
        return response

    async def search(self, text: str) -> GeocodeResponse:
        """Full forward address search query restricted to India."""
        cache_key = make_geocode_cache_key("search", text)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        params = {
            "text": text.strip(),
            "boundary.country": "IN",
        }

        raw = await self.client.request(
            method="GET",
            path_or_url=settings.ORS_GEOCODE_SEARCH_PATH,
            params=params,
        )
        results = self._parse_pelias_features(raw)
        response = GeocodeResponse(provider="openrouteservice", results=results)

        cache.set(cache_key, response, ttl_seconds=settings.CACHE_TTL_SECONDS)
        return response

    async def reverse(self, lat: float, lng: float) -> GeocodeResponse:
        """Reverse geocoding (coordinates to street address) restricted to India."""
        cache_key = make_reverse_cache_key(lat, lng)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        params = {
            "point.lat": str(lat),
            "point.lon": str(lng),
            "boundary.country": "IN",
        }

        raw = await self.client.request(
            method="GET",
            path_or_url=settings.ORS_GEOCODE_REVERSE_PATH,
            params=params,
        )
        results = self._parse_pelias_features(raw)
        response = GeocodeResponse(provider="openrouteservice", results=results)

        cache.set(cache_key, response, ttl_seconds=settings.CACHE_TTL_SECONDS)
        return response

    def _parse_pelias_features(self, raw_data: Dict[str, any]) -> List[GeocodeResult]:
        """Transform raw Pelias GeoJSON FeatureCollection into simplified clean schema."""
        features = raw_data.get("features", [])
        results: List[GeocodeResult] = []

        for feat in features:
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [0.0, 0.0])
            # GeoJSON coordinates format is [longitude, latitude]
            lng = float(coords[0]) if len(coords) > 0 else 0.0
            lat = float(coords[1]) if len(coords) > 1 else 0.0

            props = feat.get("properties", {})
            label = props.get("label") or props.get("name") or "Unknown Location"
            locality = (
                props.get("locality")
                or props.get("city")
                or props.get("county")
                or props.get("region")
            )

            results.append(
                GeocodeResult(
                    label=label,
                    lat=lat,
                    lng=lng,
                    locality=locality,
                )
            )

        return results


geocode_service = GeocodeService()
