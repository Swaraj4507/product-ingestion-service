import csv
import json
from pathlib import Path
from typing import Iterable
from uuid import UUID

from celery.exceptions import MaxRetriesExceededError
from celery.utils.log import get_task_logger

from app.core.celery_app import celery_app
from app.core.db import get_database
from app.core.event_types import WebhookEventType
from app.core.redis_client import get_redis_client
from app.core.webhook_payloads import WebhookPayloadBuilder
from app.repository.product_repository import ProductSyncRepository
from app.repository.upload_repository import UploadSyncRepository

logger = get_task_logger(__name__)

CHUNK_SIZE = 10_000
DELETE_CHUNK_SIZE = 10_000
REDIS_KEY_TEMPLATE = "upload:{task_id}"
MAX_TASK_RETRIES = 3
MAX_RETRY_DELAY_SECONDS = 60


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


def _schedule_retry(task, exc, task_uuid: UUID, processed: int, total: int) -> None:
    max_retries = task.max_retries or 0
    current_retry = task.request.retries or 0
    if current_retry >= max_retries:
        raise MaxRetriesExceededError(f"Max retries exceeded for task {task_uuid}") from exc

    attempt = current_retry + 1
    delay = min(MAX_RETRY_DELAY_SECONDS, 2 ** attempt)
    logger.warning(
        "Task %s failed (attempt %s/%s): %s. Retrying in %s seconds.",
        task_uuid,
        attempt,
        max_retries,
        exc,
        delay,
    )
    _update_redis(task_uuid, "retrying", processed, total)
    raise task.retry(exc=exc, countdown=delay)


def _mark_failed(database, task_uuid: UUID, processed: int, total: int, reason: str) -> None:
    with database.sync_session() as session:
        upload_repo = UploadSyncRepository(session)
        upload_repo.mark_failed(task_uuid, reason=reason)
    _update_redis(task_uuid, "failed", processed, total)


def _mark_completed(database, task_uuid: UUID, processed: int, total: int) -> None:
    with database.sync_session() as session:
        upload_repo = UploadSyncRepository(session)
        upload_repo.mark_completed(task_uuid)
    _update_redis(task_uuid, "completed", processed, total)


@celery_app.task(
    name="app.tasks.product_tasks.import_products_from_csv",
    bind=True,
    max_retries=MAX_TASK_RETRIES,
    acks_late=True,
    reject_on_worker_lost=True,
)
def import_products_from_csv(self, task_id: str, file_path: str) -> None:
    task_uuid = UUID(task_id)
    path = Path(file_path)
    if not path.exists():
        logger.error("Upload file not found for task %s: %s", task_id, file_path)
        database = get_database()
        _mark_failed(database, task_uuid, 0, 0, "Upload file not found.")
        return

    database = get_database()
    with database.sync_session() as session:
        upload_repo = UploadSyncRepository(session)
        upload = upload_repo.get_by_task_id(task_uuid)
        stored_total = upload.total_records
        processed_records = upload.processed_records

    total_records = stored_total or _load_total_records(path)

    with database.sync_session() as session:
        upload_repo = UploadSyncRepository(session)
        upload_repo.mark_processing(
            task_uuid,
            total_records,
            initial_processed=processed_records,
        )

    processed_records = min(processed_records, total_records)
    if total_records == 0 or processed_records >= total_records:
        logger.info("Import task %s already completed.", task_id)
        _mark_completed(database, task_uuid, processed_records, total_records)
        return

    remaining_replay = processed_records
    _update_redis(task_uuid, "in_progress", processed_records, total_records)

    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for chunk in _iter_chunks(reader):
                products = _build_product_payload(chunk)
                if not products:
                    continue

                if remaining_replay:
                    if remaining_replay >= len(products):
                        remaining_replay -= len(products)
                        continue
                    products = products[remaining_replay:]
                    remaining_replay = 0
                    if not products:
                        continue

                with database.sync_session() as session:
                    product_repo = ProductSyncRepository(session)
                    product_repo.bulk_upsert(products)

                    processed_records = min(processed_records + len(products), total_records)
                    progress = (processed_records / total_records) * 100 if total_records else 0.0

                    upload_repo = UploadSyncRepository(session)
                    upload_repo.update_progress(
                        task_uuid,
                        processed_records=processed_records,
                        total_records=total_records,
                        progress=progress,
                    )

                _update_redis(task_uuid, "in_progress", processed_records, total_records)
                logger.info("Processed %d/%d products for task %s", processed_records, total_records, task_id)
        _mark_completed(database, task_uuid, processed_records, total_records)

        event_type = WebhookEventType.PRODUCT_UPLOAD_COMPLETE.value
        payload_data = WebhookPayloadBuilder.build_payload_data(event_type, total_products=processed_records)
        celery_app.send_task(
            "app.tasks.webhook_tasks.trigger_webhooks",
            args=[event_type, payload_data],
        )

    except Exception as exc:  # pragma: no cover - defensive
        try:
            _schedule_retry(self, exc, task_uuid, processed_records, total_records)
        except MaxRetriesExceededError:
            logger.exception("Failed to import products for task %s", task_id, exc_info=exc)
            _mark_failed(database, task_uuid, processed_records, total_records, str(exc))
            raise


@celery_app.task(
    name="app.tasks.product_tasks.bulk_delete_products",
    bind=True,
    max_retries=MAX_TASK_RETRIES,
    acks_late=True,
    reject_on_worker_lost=True,
)
def bulk_delete_products(self, task_id: str) -> None:
    task_uuid = UUID(task_id)
    database = get_database()
    processed_records = 0
    total_records = 0

    try:
        with database.sync_session() as session:
            product_repo = ProductSyncRepository(session)
            remaining_records = product_repo.count_all()

            upload_repo = UploadSyncRepository(session)
            upload = upload_repo.get_by_task_id(task_uuid)
            processed_records = min(upload.processed_records, upload.total_records or 0)

            if upload.total_records:
                total_records = upload.total_records
            else:
                total_records = processed_records + remaining_records

            upload_repo.mark_processing(
                task_uuid,
                total_records,
                initial_processed=processed_records,
            )

            if remaining_records == 0 or processed_records >= total_records:
                upload_repo.mark_completed(task_uuid)
                _update_redis(task_uuid, "completed", processed_records, total_records)
                logger.info("No products to delete for task %s", task_id)
                return

        current_remaining = remaining_records
        _update_redis(task_uuid, "in_progress", processed_records, total_records)

        while current_remaining > 0:
            with database.sync_session() as session:
                product_repo = ProductSyncRepository(session)
                deleted_count = product_repo.delete_chunk(DELETE_CHUNK_SIZE)

                if deleted_count == 0:
                    current_remaining = product_repo.count_all()
                    if current_remaining == 0:
                        break
                    continue

                processed_records = min(processed_records + deleted_count, total_records)
                current_remaining = max(current_remaining - deleted_count, 0)
                progress = (processed_records / total_records) * 100 if total_records else 0.0

                upload_repo = UploadSyncRepository(session)
                upload_repo.update_progress(
                    task_uuid,
                    processed_records=processed_records,
                    total_records=total_records,
                    progress=progress,
                )

            _update_redis(task_uuid, "in_progress", processed_records, total_records)
            logger.info("Deleted %d/%d products for task %s", processed_records, total_records, task_id)

        _mark_completed(database, task_uuid, processed_records, total_records)
        logger.info("Bulk delete completed for task %s: %d products deleted", task_id, processed_records)

        event_type = WebhookEventType.BULK_DELETE_COMPLETE.value
        payload_data = WebhookPayloadBuilder.build_payload_data(event_type, deleted_count=processed_records)
        celery_app.send_task(
            "app.tasks.webhook_tasks.trigger_webhooks",
            args=[event_type, payload_data],
        )

    except Exception as exc:  # pragma: no cover - defensive
        try:
            _schedule_retry(self, exc, task_uuid, processed_records, total_records)
        except MaxRetriesExceededError:
            logger.exception("Failed to bulk delete products for task %s", task_id, exc_info=exc)
            _mark_failed(database, task_uuid, processed_records, total_records, str(exc))
            raise

