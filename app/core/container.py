from functools import lru_cache

from app.core.celery_app import celery_app
from app.core.db import Database, get_database
from app.core.redis_client import RedisClient, get_redis_client
from app.core.settings import AppSettings, get_settings
from app.repository.health_repository import HealthRepository
from app.services.health_service import HealthService
from app.services.product_service import ProductService
from app.services.webhook_service import WebhookService


class ServiceContainer:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._database = get_database()
        self._redis_client = get_redis_client()
        self._celery_app = celery_app

        # Repositories
        self._health_repository = HealthRepository()

        # Services (singletons)
        self._health_service = HealthService(self._health_repository)
        self._product_service = ProductService()
        self._webhook_service = WebhookService()

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @property
    def database(self) -> Database:
        return self._database

    @property
    def health_service(self) -> HealthService:
        return self._health_service

    @property
    def product_service(self) -> ProductService:
        return self._product_service

    @property
    def webhook_service(self) -> WebhookService:
        return self._webhook_service

    @property
    def redis_client(self) -> RedisClient:
        return self._redis_client

    @property
    def celery_app(self):
        return self._celery_app


@lru_cache(maxsize=1)
def get_container() -> ServiceContainer:
    return ServiceContainer(get_settings())

