"""Runtime configuration, loaded from environment variables with the ``LG_`` prefix."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LG_", env_file=".env", extra="ignore")

    anomaly_min_cents: int = 1000
    anomaly_z_threshold: float = 3.5
    categoriser_min_confidence: float = 0.45


def get_settings() -> Settings:
    return Settings()
