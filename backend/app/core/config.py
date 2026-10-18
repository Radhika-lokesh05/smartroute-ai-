from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings read from environment variables or .env file."""

    PROJECT_NAME: str = "SmartRoute AI"
    API_V1_STR: str = "/api/v1"

    # Database settings
    # Neon asyncpg format: postgresql+asyncpg://USER:PASSWORD@HOST/DBNAME?ssl=require
    DATABASE_URL: str = "postgresql+asyncpg://neondb_owner:password@ep-placeholder.us-east-2.aws.neon.tech/neondb?ssl=require"

    # External APIs
    ORS_API_KEY: str = ""

    # Security
    JWT_SECRET: str = "smartroute_ai_insecure_development_secret_key_32chars"

    # CORS
    ALLOWED_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

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
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
