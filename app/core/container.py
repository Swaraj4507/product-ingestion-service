from functools import lru_cache

from app.core.db import Database, get_database
from app.core.settings import AppSettings, get_settings
from app.repository.health_repository import HealthRepository
from app.service.health_service import HealthService


class ServiceContainer:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._database = get_database()

        # Repositories
        self._health_repository = HealthRepository()

        # Services
        self._health_service = HealthService(self._health_repository)

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @property
    def database(self) -> Database:
        return self._database

    @property
    def health_service(self) -> HealthService:
        return self._health_service


@lru_cache(maxsize=1)
def get_container() -> ServiceContainer:
    return ServiceContainer(get_settings())

