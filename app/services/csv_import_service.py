import csv
import io
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import ServiceContainer
from app.core.redis_client import RedisClient
from app.models.upload import Upload, UploadStatus
from app.repository.upload_repository import UploadRepository


class UploadNotFoundError(LookupError):
    """Raised when an upload could not be located."""


class CSVValidationError(ValueError):
    """Raised when the uploaded CSV is invalid."""


@dataclass(frozen=True)
class UploadListResult:
    total: int
    page: int
    limit: int
    items: list[Upload]


class CSVImportService:
    REQUIRED_COLUMNS = {"name", "sku", "description"}
    UPLOAD_DIRECTORY = Path("/tmp/uploads")
    REDIS_UPLOAD_KEY_TEMPLATE = "upload:{task_id}"

    def __init__(self, container: ServiceContainer) -> None:
        self._container = container
        self._redis_client: RedisClient = container.redis_client
        self._celery_app = container.celery_app

    async def enqueue_import(self, upload_file: UploadFile, session: AsyncSession) -> UUID:
        self._validate_file_extension(upload_file.filename)
        await self._validate_csv_columns(upload_file)

        self.UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
        task_id = uuid4()
        stored_file_path = await self._persist_file(upload_file, task_id)

        repository = UploadRepository(session)
        await repository.create_upload(task_id, upload_file.filename)
        await session.commit()

        self._celery_app.send_task(
            "app.tasks.product_tasks.import_products_from_csv",
            args=[str(task_id), str(stored_file_path)],
        )

        await self._cache_initial_progress(task_id)
        return task_id

    async def get_status(self, task_id: UUID, session: AsyncSession) -> dict[str, Any]:
        redis_key = self.REDIS_UPLOAD_KEY_TEMPLATE.format(task_id=task_id)
        async_client = self._redis_client.get_async_client()
        cached = await async_client.get(redis_key)
        if cached:
            payload = json.loads(cached)
            processed = int(payload.get("processed", 0))
            total = int(payload.get("total", 0))
            return {
                "status": payload.get("status", "pending"),
                "processed_records": processed,
                "total_records": total,
                "progress_percentage": round(self._calculate_progress(processed, total), 2),
            }

        repository = UploadRepository(session)
        upload = await repository.get_by_task_id(task_id)
        if not upload:
            raise UploadNotFoundError(f"Upload with task_id {task_id} was not found.")

        status = self._map_status(upload.status)
        progress_percentage = round(self._calculate_progress(upload.processed_records, upload.total_records), 2)
        return {
            "status": status,
            "processed_records": upload.processed_records,
            "total_records": upload.total_records,
            "progress_percentage": progress_percentage,
        }

    async def list_uploads(
        self,
        session: AsyncSession,
        *,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> UploadListResult:
        repository = UploadRepository(session)
        uploads, total = await repository.list_uploads(status=status, page=page, limit=limit)
        return UploadListResult(total=total, page=page, limit=limit, items=uploads)

    async def _validate_csv_columns(self, upload_file: UploadFile) -> None:
        upload_file.file.seek(0)
        header_bytes = upload_file.file.readline()
        upload_file.file.seek(0)

        if not header_bytes:
            raise CSVValidationError("CSV file does not contain a header row.")

        try:
            header_line = header_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise CSVValidationError("CSV file must be UTF-8 encoded.") from exc

        reader = csv.reader(io.StringIO(header_line))
        header = next(reader, None)

        if not header:
            raise CSVValidationError("CSV file does not contain a header row.")

        normalized_columns = {column.strip().lower() for column in header}
        missing_columns = self.REQUIRED_COLUMNS - normalized_columns
        if missing_columns:
            raise CSVValidationError(f"CSV file is missing required columns: {', '.join(sorted(missing_columns))}")

    async def _persist_file(self, upload_file: UploadFile, task_id: UUID) -> Path:
        safe_filename = self._sanitize_filename(upload_file.filename)
        destination = self.UPLOAD_DIRECTORY / f"{task_id}_{safe_filename}"

        upload_file.file.seek(0)
        with destination.open("wb") as file_buffer:
            while True:
                chunk = await upload_file.read(1024 * 1024)
                if not chunk:
                    break
                file_buffer.write(chunk)
        upload_file.file.seek(0)

        return destination

    async def _cache_initial_progress(self, task_id: UUID) -> None:
        async_client = self._redis_client.get_async_client()
        await async_client.set(
            self.REDIS_UPLOAD_KEY_TEMPLATE.format(task_id=task_id),
            json.dumps({"status": UploadStatus.PENDING, "processed": 0, "total": 0}),
        )

    @staticmethod
    def _map_status(status: str) -> str:
        mapping = {
            UploadStatus.PENDING: "pending",
            UploadStatus.PROCESSING: "in_progress",
            UploadStatus.COMPLETED: "completed",
            UploadStatus.FAILED: "failed",
        }
        return mapping.get(status, status)

    @staticmethod
    def _calculate_progress(processed: int, total: int) -> float:
        if not total:
            return 0.0
        return (processed / total) * 100

    @staticmethod
    def _validate_file_extension(filename: str | None) -> None:
        if not filename or not filename.lower().endswith(".csv"):
            raise CSVValidationError("Only CSV files are supported.")

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        return Path(filename).name.replace(" ", "_")

