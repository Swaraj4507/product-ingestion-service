from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UploadStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

    @classmethod
    def all(cls) -> tuple[str, ...]:
        return cls.PENDING, cls.PROCESSING, cls.COMPLETED, cls.FAILED


class Upload(Base):
    __tablename__ = "file_uploads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        default=uuid4,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=UploadStatus.PENDING)
    processed_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def mark_processing(self, total_records: int) -> None:
        self.status = UploadStatus.PROCESSING
        self.total_records = total_records

    def mark_completed(self) -> None:
        self.status = UploadStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.progress = 100

    def mark_failed(self) -> None:
        self.status = UploadStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)


