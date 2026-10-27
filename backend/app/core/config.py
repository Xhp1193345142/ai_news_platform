from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Signal API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"]
    )
    database_url: str = "postgresql+asyncpg://ai_signal:change-me@localhost:5432/ai_signal"
    sync_database_url: str = "postgresql+psycopg://ai_signal:change-me@localhost:5432/ai_signal"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "ai_signal_admin"
    s3_secret_key: str = "change-me-minio-secret"
    s3_public_bucket: str = "ai-signal-public"
    s3_archive_bucket: str = "ai-signal-archive"
    s3_region: str = "us-east-1"
    openai_cookie: SecretStr | None = None
    jwt_secret_key: str = "replace-with-a-long-random-secret-before-use"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        """Accept the comma-separated form used in `.env.example`."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
