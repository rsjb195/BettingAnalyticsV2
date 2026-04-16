"""
Application configuration loaded from environment variables.

All settings are validated at startup via Pydantic Settings.
Secrets are never logged or exposed in error messages.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the football quant analytics platform."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database ---
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/football_quant"
    database_url_sync: str = "postgresql://user:password@localhost:5432/football_quant"
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_recycle: int = 3600

    # --- FootyStats API ---
    footystats_api_key: str = ""
    footystats_base_url: str = "https://api.football-data-api.com"
    footystats_requests_per_hour: int = 3600
    footystats_request_delay: float = 1.0  # seconds between requests

    # --- Redis / Caching ---
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_hours: int = 24

    # --- Application ---
    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    timezone: str = "Europe/London"

    # --- Staking ---
    default_stake: float = 50.0
    target_odds_low: float = 25.0
    target_odds_high: float = 40.0

    # --- Paths ---
    csv_data_dir: str = "data/csvs"
    log_dir: str = "logs"

    # --- English Leagues ---
    # These are populated at runtime by the bootstrap script via /league-list.
    # Defaults are empty; the bootstrap discovers and persists them.
    english_league_tiers: dict = {
        1: "Premier League",
        2: "Championship",
        3: "League One",
        4: "League Two",
    }

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
