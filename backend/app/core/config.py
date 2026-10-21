import re
from pathlib import Path
from typing import List, Optional, Tuple, Union
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def clean_neon_asyncpg_url(url: Optional[str]) -> Optional[str]:
    """
    Sanitize database URL for asyncpg:
    - Ensures postgresql+asyncpg:// scheme
    - Fixes accidental duplicate path fragments from Neon dashboard copy-paste
    - Removes asyncpg-incompatible query parameters ('sslmode', 'channel_binding')
    - Ensures 'ssl=require' is present
    """
    if not url or not url.strip():
        return url
    
    clean_url = url.strip()

    # Fix accidental duplicate path/query concatenation e.g. ".../neondb?sslmode=.../neondb?ssl=require"
    if "/neondb" in clean_url and clean_url.count("/neondb") > 1:
        match = re.search(r"^(.*?/neondb)(?:[/?].*?)(?:\?.*)?$", clean_url)
        if match:
            clean_url = match.group(1) + "?ssl=require"

    # Ensure postgresql+asyncpg:// scheme
    if clean_url.startswith("postgres://"):
        clean_url = "postgresql+asyncpg://" + clean_url[len("postgres://"):]
    elif clean_url.startswith("postgresql://") and not clean_url.startswith("postgresql+asyncpg://"):
        clean_url = "postgresql+asyncpg://" + clean_url[len("postgresql://"):]

    try:
        parsed = urlparse(clean_url)
        qs = parse_qs(parsed.query)
        # Remove asyncpg-incompatible parameters that Neon UI includes
        # Enforce ssl=require for Neon and remote cloud postgres, but allow non-SSL for localhost/CI Docker
        hostname = (parsed.hostname or "").lower()
        if any(h in hostname for h in ("neon.tech", "render.com", "aws")):
            qs["ssl"] = ["require"]
        elif hostname in ("localhost", "127.0.0.1", "postgres"):
            qs.pop("ssl", None)

        new_query = urlencode(qs, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return clean_url


class Settings(BaseSettings):
    """Application settings read from environment variables or .env file."""

    PROJECT_NAME: str = "SmartRoute AI"
    API_V1_STR: str = "/api/v1"
    BACKEND_DIR: Path = BACKEND_DIR

    # Database settings
    # Neon asyncpg format: postgresql+asyncpg://USER:PASSWORD@HOST/DBNAME?ssl=require
    DATABASE_URL: str = "postgresql+asyncpg://neondb_owner:password@ep-placeholder.us-east-2.aws.neon.tech/neondb?ssl=require"

    # Test Database URL (strictly isolated for pytest suite)
    TEST_DATABASE_URL: Optional[str] = None

    # OpenRouteService / HeiGIT API Configuration
    ORS_API_KEY: str = ""
    ORS_BASE_URL: str = "https://api.heigit.org"
    ORS_DIRECTIONS_PATH: str = "/openrouteservice/v2/directions/driving-car/geojson"
    ORS_GEOCODE_AUTOCOMPLETE_PATH: str = "/pelias/v1/autocomplete"
    ORS_GEOCODE_SEARCH_PATH: str = "/pelias/v1/search"
    ORS_GEOCODE_REVERSE_PATH: str = "/pelias/v1/reverse"

    # Routing Fallback (OSRM Demo Server)
    ROUTING_FALLBACK_ENABLED: bool = False
    OSRM_BASE_URL: str = "https://router.project-osrm.org"
    OSRM_DIRECTIONS_PATH: str = "/route/v1/driving"

    # In-memory Caching Configuration
    CACHE_TTL_SECONDS: int = 300
    CACHE_MAX_SIZE: int = 2000

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Incident Lifecycle & Voting Configuration
    INCIDENT_TTL_MINUTES: int = 45
    INCIDENT_VOTE_RADIUS_M: float = 1000.0
    INCIDENT_DEDUPE_RADIUS_M: float = 100.0
    VALIDATION_THRESHOLD: int = 3
    REJECTION_THRESHOLD: int = 3
    MAX_REPORTS_PER_10_MIN: int = 3
    MAX_VOTES_PER_HOUR: int = 30
    CIVILIAN_CONFIRM_WEIGHT: float = 1.0
    AMBULANCE_CONFIRM_WEIGHT: float = 2.0
    ADMIN_CONFIRM_WEIGHT: float = 3.0

    # Incident-Aware Routing & Penalties Configuration
    INCIDENT_ROUTE_BUFFER_M: float = 100.0
    AVOID_POLYGON_RADIUS_M: float = 150.0
    MAX_AVOID_INCIDENTS: int = 10
    PENALTY_ACCIDENT_S: int = 600
    PENALTY_BLOCKAGE_S: int = 900
    PENALTY_HAZARD_S: int = 180
    PENDING_INCIDENT_WEIGHT: float = 0.4
    ROUTE_CACHE_TTL_WITH_INCIDENTS_S: int = 30

    # Weather & Open-Meteo Configuration
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"
    WEATHER_CACHE_TTL_S: int = 900

    # Traffic ML Model & Zone Lookup Configuration
    TRAFFIC_MODEL_PATH: str = "ml/artifacts/model.joblib"
    TRAFFIC_ZONES_PATH: str = "ml/zones.json"
    ZONE_RADIUS_MARGIN_KM: float = 1.0

    # Overpass & Hospital Routing Configuration
    OVERPASS_URL: str = "https://overpass-api.de/api/interpreter"
    HOSPITAL_SEARCH_RADIUS_M: float = 15000.0
    HOSPITAL_PREFILTER_COUNT: int = 6
    HOSPITAL_ROUTE_COUNT: int = 3
    BENGALURU_BBOX: Tuple[float, float, float, float] = (12.80, 77.40, 13.15, 77.80)

    # Ambulance Tracking & Proximity Warning
    AMBULANCE_LOCATION_MIN_INTERVAL_S: float = 2.0
    AMBULANCE_LOCATION_STALE_S: float = 30.0
    AMBULANCE_DB_FLUSH_S: float = 15.0
    AMBULANCE_WARN_RADIUS_M: float = 1500.0
    CIVILIAN_WARN_MIN_INTERVAL_S: float = 5.0

    # Dispatch Configuration
    DISPATCH_CANDIDATE_RADIUS_M: float = 10000.0
    DISPATCH_CANDIDATE_ROUTE_COUNT: int = 3
    DISPATCH_OFFER_TIMEOUT_S: float = 60.0
    DISPATCH_MAX_OFFERS_PER_INCIDENT: int = 5
    EMERGENCY_NUMBER: str = "112"

    # Realtime WebSocket Configuration

    WS_MAX_CONNECTIONS_PER_USER: int = 3
    WS_AUTH_TIMEOUT_S: float = 5.0
    MAX_SUBSCRIBE_RADIUS_M: float = 20000.0

    # Environment mode: 'development' | 'production'
    ENV: str = "development"
    TRUSTED_PROXY_HOPS: int = 1

    # Security & Authentication
    JWT_SECRET: str = "smartroute_ai_insecure_development_secret_key_32chars"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Initial Admin Seeding (for scripts/seed_admin.py)
    ADMIN_EMAIL: Optional[str] = "admin@smartroute.ai"
    ADMIN_PASSWORD: Optional[str] = None

    # Admin Management & Metrics Configuration
    ADMIN_PAGE_SIZE_MAX: int = 100
    METRICS_DEFAULT_DAYS: int = 7
    METRICS_MAX_DAYS: int = 90
    HEATMAP_GRID_M: float = 250.0
    MAX_ROUTE_CALLS: int = 50

    # CORS
    ALLOWED_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    def validate_production_security(self) -> None:
        """
        In production, enforce strict security rules and refuse startup if insecure.
        Never logs or prints secret values.
        """
        if self.ENV.lower() != "production":
            return

        import logging
        log = logging.getLogger("smartroute.security")

        # 1. DATABASE_URL must be configured
        if not self.DATABASE_URL or "placeholder" in self.DATABASE_URL:
            log.critical("[FATAL CONFIG] Production requires a valid, non-placeholder DATABASE_URL.")
            raise RuntimeError("Production configuration error: DATABASE_URL is missing or placeholder.")

        # 2. JWT_SECRET checks: >= 32 chars, not placeholder
        if not self.JWT_SECRET or len(self.JWT_SECRET) < 32:
            log.critical("[FATAL CONFIG] Production JWT_SECRET is missing or shorter than 32 characters.")
            raise RuntimeError("Production configuration error: JWT_SECRET must be at least 32 characters.")

        placeholders = [
            "your_jwt_secret_key_minimum_32_characters_long",
            "smartroute_ai_insecure_development_secret_key_32chars",
            "change-this",
            "changethis",
            "placeholder",
            "secret",
        ]
        secret_lower = self.JWT_SECRET.lower()
        for p in placeholders:
            if p == secret_lower or (len(p) > 10 and p in secret_lower):
                log.critical("[FATAL CONFIG] Production JWT_SECRET matches a known insecure placeholder from template.")
                raise RuntimeError("Production configuration error: JWT_SECRET must not use template placeholder values.")

        # 3. ALLOWED_ORIGINS checks: no wildcard, no non-localhost http://
        origins = self.ALLOWED_ORIGINS if isinstance(self.ALLOWED_ORIGINS, list) else [self.ALLOWED_ORIGINS]
        if "*" in origins:
            log.critical("[FATAL CONFIG] Production ALLOWED_ORIGINS must not contain wildcard '*'.")
            raise RuntimeError("Production configuration error: Wildcard '*' forbidden in production CORS.")

        for origin in origins:
            p = urlparse(origin)
            if p.scheme == "http" and p.hostname not in ("localhost", "127.0.0.1", "::1"):
                log.critical("[FATAL CONFIG] Production ALLOWED_ORIGINS contains non-secure HTTP origin for external host.")
                raise RuntimeError(f"Production configuration error: Non-HTTPS origin forbidden in production ({origin}).")

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        return clean_neon_asyncpg_url(value) or value

    @field_validator("TEST_DATABASE_URL", mode="before")
    @classmethod
    def validate_test_database_url(cls, value: Optional[str]) -> Optional[str]:
        if value:
            return clean_neon_asyncpg_url(value)
        return value

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            if not value.strip():
                return []
            if value.startswith("[") and value.endswith("]"):
                import json
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        elif isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return []

    model_config = SettingsConfigDict(
        env_file=[".env", str(BACKEND_DIR / ".env")],
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
