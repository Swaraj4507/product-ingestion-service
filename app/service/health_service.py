from app.repository.health_repository import HealthRepository


class HealthService:
    def __init__(self, health_repository: HealthRepository) -> None:
        self._health_repository = health_repository

    async def get_status(self) -> dict[str, str]:
        return await self._health_repository.fetch_status()
