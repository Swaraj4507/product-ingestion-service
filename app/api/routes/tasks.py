from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import ServiceContainer, get_container
from app.core.db import get_async_session
from app.schemas.response_schema import ApiResponse
from app.services.csv_import_service import CSVImportService, UploadNotFoundError

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _get_service(container: ServiceContainer = Depends(get_container)) -> CSVImportService:
    return CSVImportService(container)


@router.get("/{task_id}")
async def get_task_status(
    task_id: UUID,
    service: CSVImportService = Depends(_get_service),
    session: AsyncSession = Depends(get_async_session),
) -> ApiResponse[dict[str, object]]:
    try:
        status_data = await service.get_status(task_id, session)
        task_status = {
            "task_id": str(task_id),
            "status": status_data["status"],
            "progress": status_data["progress_percentage"],
            "processed_records": status_data["processed_records"],
            "total_records": status_data["total_records"],
        }
    except UploadNotFoundError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc

    return ApiResponse(
        message="Task status retrieved successfully",
        results=task_status,
    )

