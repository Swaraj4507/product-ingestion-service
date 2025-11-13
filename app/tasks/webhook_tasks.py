from datetime import datetime, timezone
from typing import Any

import httpx
from celery.utils.log import get_task_logger

from app.core.celery_app import celery_app
from app.core.db import get_database
from app.repository.webhook_repository import WebhookSyncRepository

logger = get_task_logger(__name__)

HTTP_TIMEOUT = 30.0


@celery_app.task(name="app.tasks.webhook_tasks.trigger_webhooks", bind=True)
def trigger_webhooks(self, event_type: str, payload: dict[str, Any]) -> None:
    database = get_database()

    try:
        with database.sync_session() as session:
            webhook_repo = WebhookSyncRepository(session)
            webhooks = webhook_repo.get_active_by_event_type(event_type)

        if not webhooks:
            logger.info("No active webhooks found for event_type: %s", event_type)
            return

        logger.info("Triggering %d webhook(s) for event_type: %s", len(webhooks), event_type)

        webhook_payload = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": payload,
        }

        for webhook in webhooks:
            try:
                start_time = datetime.now(timezone.utc)
                with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                    response = client.post(webhook.url, json=webhook_payload)
                    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

                    logger.info(
                        "Webhook %s (%s): %s %s (%.2fs)",
                        webhook.id,
                        webhook.name,
                        response.status_code,
                        webhook.url,
                        elapsed,
                    )

                    if response.status_code >= 400:
                        logger.warning(
                            "Webhook %s (%s) failed with status %d: %s",
                            webhook.id,
                            webhook.name,
                            response.status_code,
                            response.text[:200],
                        )

            except httpx.TimeoutException:
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.error(
                    "Webhook %s (%s) timed out after %.2fs: %s",
                    webhook.id,
                    webhook.name,
                    elapsed,
                    webhook.url,
                )

            except httpx.RequestError as exc:
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.error(
                    "Webhook %s (%s) request error after %.2fs: %s - %s",
                    webhook.id,
                    webhook.name,
                    elapsed,
                    webhook.url,
                    str(exc),
                )

            except Exception as exc:
                logger.exception(
                    "Unexpected error triggering webhook %s (%s): %s",
                    webhook.id,
                    webhook.name,
                    webhook.url,
                )

    except Exception as exc:
        logger.exception("Failed to trigger webhooks for event_type: %s", event_type)
        raise

