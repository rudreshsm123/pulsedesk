from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PulseDesk"
    environment: str = "dev"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://pulsedesk:pulsedesk@localhost:5432/pulsedesk"
    redis_url: str = "redis://localhost:6379/0"

    # RFC 7518 3.2 recommends >=32 bytes for an HS256 key; this placeholder is that
    # long purely to avoid PyJWT's InsecureKeyLengthWarning in dev -- it is still a
    # placeholder and must be overridden via JWT_SECRET_KEY in any real deployment.
    jwt_secret_key: str = "change-me-in-production-min-32-bytes-long"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    llm_provider: str = "mock"  # "mock" or "anthropic"
    llm_api_key: str | None = None
    # Small/cheap model for classification (runs on every ticket), larger model only for
    # the resolution draft (Part 5's cost-control strategy: cheap model for the
    # high-volume path, better model only where quality actually matters).
    llm_classify_model: str = "claude-haiku-4-5-20251001"
    llm_resolution_model: str = "claude-sonnet-5"

    default_sla_hours: int = 24
    rate_limit_per_minute: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
