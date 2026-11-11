"""Application settings (12-factor, APP_* environment variables)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# services/api - env files are resolved from the package, not from the cwd, so
# scripts and uvicorn behave the same no matter where they are launched from.
API_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All runtime configuration lives here; nothing else reads os.environ."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=(str(API_ROOT / ".env"), str(API_ROOT / ".env.local")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- identity ----------------------------------------------------------
    app_name: str = "کاروند"
    app_version: str = "0.1.0"
    app_env: Literal["dev", "prod"] = "dev"
    debug: bool = True
    api_prefix: str = "/v1"

    # --- database ----------------------------------------------------------
    database_url: str = "postgresql+asyncpg://openbot_app:openbot@127.0.0.1:5432/openbot"
    migration_database_url: str | None = None
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # --- security ----------------------------------------------------------
    jwt_secret: str = "dev-only-change-me"
    jwt_alg: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 7
    master_key: str = ""

    # --- persian / locale defaults -----------------------------------------
    default_locale: str = "fa"
    default_timezone: str = "Asia/Tehran"
    default_calendar: Literal["jalali", "gregorian"] = "jalali"
    default_currency: str = "IRR"
    default_digits: Literal["fa", "en"] = "fa"
    fx_usd_irr: int = 0

    # --- commercial flags (phase 1: free mode, no payment gateway) ----------
    free_mode: bool = True
    billing_enabled: bool = False
    payment_gateway: str = "noop"

    # --- scheduler (cron worker, see ``python -m app.workers.scheduler``) --
    scheduler_enabled: bool = False
    scheduler_tick_seconds: int = 30
    scheduler_max_concurrency: int = 2
    scheduler_lock_key: int = 982_451_653
    scheduler_timezone: str = "Asia/Tehran"
    scheduler_min_gap_seconds: int = 50

    # --- http --------------------------------------------------------------
    cors_origins: list[str] = ["http://localhost:3000"]
    # public origin used to build absolute webhook URLs (https://api.example.com);
    # empty means "derive from the incoming request", which is fine locally only.
    public_base_url: str = ""

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @property
    def effective_migration_url(self) -> str:
        return self.migration_database_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
