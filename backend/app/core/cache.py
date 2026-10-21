import hashlib
import json
import re
import threading
import time
from typing import Any, Dict, Optional, Tuple
from app.core.config import settings

# NOTE: Simple in-memory TTL cache for development and single-instance deployments.
# As the SmartRoute AI infrastructure scales across multiple instances or workers,
# this cache layer will move to a distributed Redis cluster.


class InMemoryTTLCache:
    """Thread-safe in-memory cache with Time-To-Live (TTL) expiration and max capacity."""

    def __init__(self, max_size: int = 2000, default_ttl: int = 300) -> None:
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, Tuple[float, Any]] = {}  # key -> (expires_at, value)
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value if key exists and has not expired."""
        with self._lock:
            if key not in self._cache:
                return None
            expires_at, value = self._cache[key]
            if time.time() > expires_at:
                del self._cache[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store value with expiration. Evicts expired or oldest entries if capacity is reached."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expires_at = time.time() + ttl

        with self._lock:
            now = time.time()
            # If at capacity, purge expired entries first
            if len(self._cache) >= self.max_size and key not in self._cache:
                expired_keys = [k for k, (exp, _) in self._cache.items() if now > exp]
                for k in expired_keys:
                    del self._cache[k]

                # If still at capacity, evict the oldest inserted key
                if len(self._cache) >= self.max_size:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]

            self._cache[key] = (expires_at, value)

    def clear(self) -> None:
        """Clear all entries from cache (used in testing)."""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Return number of currently stored entries."""
        with self._lock:
            return len(self._cache)


# Global cache instance
cache = InMemoryTTLCache(
    max_size=settings.CACHE_MAX_SIZE,
    default_ttl=settings.CACHE_TTL_SECONDS,
)


def normalize_query_text(text: str) -> str:
    """Normalize search query: lowercase, collapse whitespaces, strip punctuation edges."""
    cleaned = re.sub(r"\s+", " ", text.lower().strip())
    return cleaned


def make_route_cache_key(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    avoid_polygons: Optional[Any] = None,
    incidents_hash: Optional[str] = None,
    model_version: Optional[str] = None,
    date_bucket: Optional[str] = None,
    weather_condition: Optional[str] = None,
) -> str:
    """Create normalized cache key for routing with coordinates, incidents, model version, date, and weather."""
    o_lat = round(origin_lat, 5)
    o_lng = round(origin_lng, 5)
    d_lat = round(dest_lat, 5)
    d_lng = round(dest_lng, 5)

    avoid_str = ""
    if avoid_polygons:
        avoid_json = json.dumps(avoid_polygons, sort_keys=True)
        avoid_str = f":avoid={hashlib.sha256(avoid_json.encode('utf-8')).hexdigest()[:12]}"

    inc_str = f":inc={incidents_hash}" if incidents_hash else ""
    ml_str = f":ml={model_version or 'nomodel'}:{date_bucket or 'nodate'}:{weather_condition or 'noweather'}"
    return f"route:{o_lat},{o_lng}->{d_lat},{d_lng}{avoid_str}{inc_str}{ml_str}"


def make_geocode_cache_key(prefix: str, text: str, focus_lat: Optional[float] = None, focus_lng: Optional[float] = None) -> str:
    """Create normalized cache key for geocoding queries."""
    norm_text = normalize_query_text(text)
    focus_str = ""
    if focus_lat is not None and focus_lng is not None:
        focus_str = f":focus={round(focus_lat, 5)},{round(focus_lng, 5)}"
    return f"geo:{prefix}:{norm_text}{focus_str}"


def make_reverse_cache_key(lat: float, lng: float) -> str:
    """Create normalized cache key for reverse geocoding with coordinates rounded to 5 decimals."""
    return f"rev:{round(lat, 5)},{round(lng, 5)}"


def make_weather_cache_key(lat: float, lng: float, at_time_str: Optional[str] = None) -> str:
    """Create normalized cache key for weather with coordinates rounded to 2 decimals (~1.1 km)."""
    r_lat = round(lat, 2)
    r_lng = round(lng, 2)
    t_str = f":t={at_time_str}" if at_time_str else ":cur"
    return f"weather:{r_lat},{r_lng}{t_str}"

