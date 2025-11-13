from http import HTTPStatus
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import ServiceContainer, get_container
from app.core.db import get_async_session
from app.schemas.response_schema import ApiResponse
from app.schemas.upload_schema import PaginatedUploads, UploadOut
from app.services.csv_import_service import CSVImportService, UploadNotFoundError

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _get_service(container: ServiceContainer = Depends(get_container)) -> CSVImportService:
    return CSVImportService(container)


@router.get("/", response_model=ApiResponse[PaginatedUploads])
async def list_tasks(
    service: CSVImportService = Depends(_get_service),
    session: AsyncSession = Depends(get_async_session),
    status: Optional[str] = Query(default=None, description="Filter by status (pending, processing, completed, failed)"),
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> ApiResponse[PaginatedUploads]:
    result = await service.list_uploads(session, status=status, page=page, limit=limit)
    paginated_data = PaginatedUploads(
        total=result.total,
        page=result.page,
        limit=result.limit,
        data=[UploadOut.model_validate(upload) for upload in result.items],
    )
    return ApiResponse(
        message="Tasks retrieved successfully",
        results=paginated_data,
    )


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

