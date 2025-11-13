from fastapi import APIRouter, Depends

from app.core.container import get_container
from app.services.health_service import HealthService

router = APIRouter(prefix="/health", tags=["health"])


def get_health_service() -> HealthService:
    return get_container().health_service


@router.get("/", summary="Health check")
async def health_check(service: HealthService = Depends(get_health_service)) -> dict[str, str]:
    return await service.get_status()


