from fastapi import APIRouter, Depends

from app.core.container import get_container
from app.schemas.response_schema import ApiResponse
from app.services.health_service import HealthService

router = APIRouter(prefix="/health", tags=["health"])


def get_health_service() -> HealthService:
    return get_container().health_service


@router.get("/", summary="Health check")
async def health_check(service: HealthService = Depends(get_health_service)) -> ApiResponse[dict[str, str]]:
    status_data = await service.get_status()
    return ApiResponse(
        message="Service is healthy",
        results=status_data,
    )


