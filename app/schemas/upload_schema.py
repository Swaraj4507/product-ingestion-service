from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UploadOut(BaseModel):
    id: UUID
    task_id: UUID
    filename: str
    status: str
    processed_records: int
    total_records: int
    progress: float
    created_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class PaginatedUploads(BaseModel):
    total: int
    page: int
    limit: int
    data: list[UploadOut]

