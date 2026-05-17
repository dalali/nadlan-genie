from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration. Loaded once from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Postgres ---
    postgres_user: str = Field("nadlan", alias="POSTGRES_USER")
    postgres_password: str = Field("nadlan", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field("nadlan", alias="POSTGRES_DB")
    postgres_host: str = Field("postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")

    # --- App behaviour ---
    listing_source: str = Field("sample", alias="LISTING_SOURCE")
    scrape_rate_limit_s: float = Field(3.0, alias="SCRAPE_RATE_LIMIT_S")
    auto_seed: bool = Field(True, alias="AUTO_SEED")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # --- Path to bundled seed CSV (inside container) ---
    seed_csv_path: str = Field("/app/data/sample_transactions.csv", alias="SEED_CSV_PATH")
    sample_listings_path: str = Field(
        "/app/data/sample_listings.json", alias="SAMPLE_LISTINGS_PATH"
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        # Alembic / sync helpers
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
