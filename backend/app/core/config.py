from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LevelMind API"
    app_env: str = "development"
    database_url: str
    supabase_url: HttpUrl
    ai_base_url: HttpUrl | None = None
    ai_api_key: SecretStr | None = None
    ai_model: str | None = None
    ai_timeout_seconds: float = Field(default=30.0, gt=0)
    cors_allowed_origins: str = "http://localhost:5173"

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_allowed_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",")]
        normalized_origins: list[str] = []
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "CORS origins must be absolute HTTP origins without paths"
                )
            normalized_origins.append(origin.rstrip("/"))

        if not normalized_origins:
            raise ValueError("At least one CORS origin must be configured")

        return ",".join(normalized_origins)

    @property
    def cors_origins(self) -> list[str]:
        return self.cors_allowed_origins.split(",")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
