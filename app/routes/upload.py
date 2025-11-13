from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import ServiceContainer, get_container
from app.core.db import get_async_session
from app.services.csv_import_service import (
    CSVImportService,
    CSVValidationError,
    UploadNotFoundError,
)

router = APIRouter(prefix="/api/upload", tags=["upload"])


def _get_service(container: ServiceContainer = Depends(get_container)) -> CSVImportService:
    return CSVImportService(container)


@router.post("/", status_code=HTTPStatus.ACCEPTED)
async def upload_csv(
    file: UploadFile = File(...),
    service: CSVImportService = Depends(_get_service),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    try:
        task_id = await service.enqueue_import(file, session)
    except CSVValidationError as exc:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)) from exc

    return {"task_id": str(task_id)}


@router.get("/status/{task_id}")
async def get_upload_status(
    task_id: UUID,
    service: CSVImportService = Depends(_get_service),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    try:
        return await service.get_status(task_id, session)
    except UploadNotFoundError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc

