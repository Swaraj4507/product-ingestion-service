from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.upload import Upload, UploadStatus


class UploadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_upload(
        self,
        task_id: UUID,
        filename: str,
    ) -> Upload:
        upload = Upload(
            task_id=task_id,
            filename=filename,
            status=UploadStatus.PENDING,
            processed_records=0,
            total_records=0,
            progress=0.0,
        )
        self._session.add(upload)
        await self._session.flush()
        return upload

    async def get_by_task_id(self, task_id: UUID) -> Optional[Upload]:
        stmt = select(Upload).where(Upload.task_id == task_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_uploads(
        self,
        *,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Upload], int]:
        page = max(page, 1)
        limit = max(min(limit, 100), 1)

        base_query = select(Upload)
        count_query = select(func.count()).select_from(Upload)

        if status:
            base_query = base_query.where(Upload.status == status)
            count_query = count_query.where(Upload.status == status)

        # Get total count
        total_result = await self._session.execute(count_query)
        total = int(total_result.scalar() or 0)

        # Apply pagination and ordering
        offset_value = (page - 1) * limit
        base_query = base_query.order_by(Upload.created_at.desc()).offset(offset_value).limit(limit)

        result = await self._session.execute(base_query)
        uploads = list(result.scalars().all())

        return uploads, total

class UploadSyncRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def mark_processing(self, task_id: UUID, total_records: int) -> None:
        upload = self._session.query(Upload).filter(Upload.task_id == task_id).one()
        upload.status = UploadStatus.PROCESSING
        upload.total_records = total_records
        upload.progress = 0.0
        upload.processed_records = 0
        upload.completed_at = None

    def update_progress(
        self,
        task_id: UUID,
        processed_records: int,
        total_records: int,
        progress: float,
    ) -> None:
        upload = self._session.query(Upload).filter(Upload.task_id == task_id).one()
        upload.processed_records = processed_records
        upload.total_records = total_records
        upload.progress = progress
        upload.status = UploadStatus.PROCESSING

    def mark_completed(self, task_id: UUID) -> None:
        upload = self._session.query(Upload).filter(Upload.task_id == task_id).one()
        upload.status = UploadStatus.COMPLETED
        upload.progress = 100
        upload.completed_at = datetime.now(timezone.utc)

    def mark_failed(self, task_id: UUID, reason: Optional[str] = None) -> None:
        upload = self._session.query(Upload).filter(Upload.task_id == task_id).one()
        upload.status = UploadStatus.FAILED
        upload.completed_at = datetime.now(timezone.utc)

