from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Product Ingestion Service"
    version: str = "0.1.0"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/product_ingestion"
    sync_database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/product_ingestion"
    database_echo: bool = False

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: Optional[str] = None
    celery_default_queue: str = "default"
    celery_prefetch_multiplier: int = 1
    redis_url: str = "redis://localhost:6379/0"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()


settings = get_settings()

