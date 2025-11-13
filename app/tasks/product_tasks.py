import csv
import json
from pathlib import Path
from typing import Iterable
from uuid import UUID

from celery.utils.log import get_task_logger

from app.core.celery_app import celery_app
from app.core.db import get_database
from app.core.redis_client import get_redis_client
from app.repository.product_repository import ProductRepository
from app.repository.upload_repository import UploadSyncRepository

logger = get_task_logger(__name__)

CHUNK_SIZE = 10_000
REDIS_KEY_TEMPLATE = "upload:{task_id}"


def _iter_chunks(reader: Iterable[dict[str, str]]) -> Iterable[list[dict[str, str]]]:
    chunk: list[dict[str, str]] = []
    for row in reader:
        chunk.append(row)
        if len(chunk) >= CHUNK_SIZE:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _load_total_records(file_path: Path) -> int:
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return sum(1 for _ in reader)


def _build_product_payload(chunk: list[dict[str, str]]) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for row in chunk:
        name = row.get("name", "").strip()
        sku = row.get("sku", "").strip()
        description = row.get("description", "").strip()
        if not name or not sku:
            continue

        payload.append(
            {
                "name": name,
                "sku": sku,
                "description": description,
                "active": True,
            }
        )
    return payload


def _update_redis(task_uuid: UUID, status: str, processed: int, total: int) -> None:
    redis_client = get_redis_client().get_sync_client()
    redis_client.set(
        REDIS_KEY_TEMPLATE.format(task_id=task_uuid),
        json.dumps(
            {
                "status": status,
                "processed": processed,
                "total": total,
            }
        ),
    )


@celery_app.task(name="app.tasks.product_tasks.import_products_from_csv", bind=True)
def import_products_from_csv(self, task_id: str, file_path: str) -> None:
    task_uuid = UUID(task_id)
    path = Path(file_path)
    if not path.exists():
        logger.error("Upload file not found for task %s: %s", task_id, file_path)
        return

    database = get_database()
    total_records = _load_total_records(path)

    processed_records = 0
    try:
        with database.sync_session() as session:
            upload_repo = UploadSyncRepository(session)
            upload_repo.mark_processing(task_uuid, total_records)

        _update_redis(task_uuid, "in_progress", processed_records, total_records)

        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for chunk in _iter_chunks(reader):
                products = _build_product_payload(chunk)
                if not products:
                    continue

                with database.sync_session() as session:
                    product_repo = ProductRepository(session)
                    product_repo.bulk_upsert(products)

                    processed_records += len(products)
                    progress = (processed_records / total_records) * 100 if total_records else 0.0

                    upload_repo = UploadSyncRepository(session)
                    upload_repo.update_progress(
                        task_uuid,
                        processed_records=processed_records,
                        total_records=total_records,
                        progress=progress,
                    )

                _update_redis(task_uuid, "in_progress", processed_records, total_records)

        with database.sync_session() as session:
            upload_repo = UploadSyncRepository(session)
            upload_repo.mark_completed(task_uuid)

        _update_redis(task_uuid, "completed", total_records, total_records)

    except Exception as exc:
        logger.exception("Failed to import products for task %s", task_id)
        with database.sync_session() as session:
            upload_repo = UploadSyncRepository(session)
            upload_repo.mark_failed(task_uuid, reason=str(exc))
        _update_redis(task_uuid, "failed", processed_records, total_records)
        raise

