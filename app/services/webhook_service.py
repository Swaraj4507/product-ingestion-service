from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_types import WebhookEventType
from app.core.webhook_payloads import WebhookPayloadBuilder
from app.repository.webhook_repository import WebhookRepository

HTTP_TIMEOUT = 30.0


class WebhookNotFoundError(LookupError):
    """Raised when a webhook could not be located."""


class WebhookService:
    def __init__(self) -> None:
        """WebhookService is a singleton - session is passed per request."""
        pass

    def get_event_types(self) -> list[dict[str, str]]:
        """Return list of available event types formatted for UI."""
        return [
            {"value": event_type, "label": event_type.replace("_", " ").title()}
            for event_type in WebhookEventType.all()
        ]

    def get_sample_payloads(self, event_type: Optional[str] = None) -> dict[str, dict[str, Any]]:
        """Return sample payloads for all event types."""
        if event_type:
            return {event_type: WebhookPayloadBuilder.get_sample_payload(event_type)}
        return {event_type: WebhookPayloadBuilder.get_sample_payload(event_type) for event_type in WebhookEventType.all()}

    async def list_webhooks(
        self,
        session: AsyncSession,
        *,
        event_type: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> list[dict]:
        repository = WebhookRepository(session)
        webhooks = await repository.list_webhooks(
            event_type=event_type,
            is_active=is_active,
        )
        return [
            {
                "id": str(webhook.id),
                "name": webhook.name,
                "url": webhook.url,
                "event_type": webhook.event_type,
                "is_active": webhook.is_active,
                "created_at": webhook.created_at.isoformat(),
                "updated_at": webhook.updated_at.isoformat(),
            }
            for webhook in webhooks
        ]

    async def create_webhook(
        self,
        session: AsyncSession,
        *,
        name: str,
        url: str,
        event_type: str,
        is_active: bool,
    ) -> dict:
        repository = WebhookRepository(session)
        webhook = await repository.create_webhook(
            name=name,
            url=url,
            event_type=event_type,
            is_active=is_active,
        )
        return {
            "id": str(webhook.id),
            "name": webhook.name,
            "url": webhook.url,
            "event_type": webhook.event_type,
            "is_active": webhook.is_active,
            "created_at": webhook.created_at.isoformat(),
            "updated_at": webhook.updated_at.isoformat(),
        }

    async def get_webhook(self, session: AsyncSession, webhook_id: UUID) -> dict:
        repository = WebhookRepository(session)
        webhook = await repository.get_by_id(webhook_id)
        if not webhook:
            raise WebhookNotFoundError(f"Webhook with id {webhook_id} not found.")

        return {
            "id": str(webhook.id),
            "name": webhook.name,
            "url": webhook.url,
            "event_type": webhook.event_type,
            "is_active": webhook.is_active,
            "created_at": webhook.created_at.isoformat(),
            "updated_at": webhook.updated_at.isoformat(),
        }

    async def update_webhook(
        self,
        session: AsyncSession,
        webhook_id: UUID,
        *,
        name: Optional[str],
        url: Optional[str],
        event_type: Optional[str],
        is_active: Optional[bool],
    ) -> dict:
        repository = WebhookRepository(session)
        webhook = await repository.get_by_id(webhook_id)
        if not webhook:
            raise WebhookNotFoundError(f"Webhook with id {webhook_id} not found.")

        updated = await repository.update_webhook(
            webhook,
            name=name,
            url=url,
            event_type=event_type,
            is_active=is_active,
        )

        return {
            "id": str(updated.id),
            "name": updated.name,
            "url": updated.url,
            "event_type": updated.event_type,
            "is_active": updated.is_active,
            "created_at": updated.created_at.isoformat(),
            "updated_at": updated.updated_at.isoformat(),
        }

    async def delete_webhook(self, session: AsyncSession, webhook_id: UUID) -> None:
        repository = WebhookRepository(session)
        webhook = await repository.get_by_id(webhook_id)
        if not webhook:
            raise WebhookNotFoundError(f"Webhook with id {webhook_id} not found.")

        await repository.delete_webhook(webhook)

    async def test_webhook(
        self,
        session: AsyncSession,
        webhook_id: UUID,
        custom_payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        repository = WebhookRepository(session)
        webhook = await repository.get_by_id(webhook_id)
        if not webhook:
            raise WebhookNotFoundError(f"Webhook with id {webhook_id} not found.")

        if not webhook.is_active:
            raise ValueError("Webhook is inactive and cannot be tested")

        if custom_payload:
            payload = custom_payload
        else:
            payload = {
                "event_type": "test_event",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"message": "Webhook test successful!"},
            }

        result: dict[str, Any] = {
            "success": False,
            "status_code": None,
            "response_time_ms": None,
            "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        start_time = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.post(webhook.url, json=payload)
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                response_time_ms = round(elapsed * 1000, 2)

                result["success"] = 200 <= response.status_code < 400
                result["status_code"] = response.status_code
                result["response_time_ms"] = response_time_ms

                if response.status_code >= 400:
                    result["error"] = f"HTTP {response.status_code}: {response.text[:200]}"

        except httpx.TimeoutException:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            response_time_ms = round(elapsed * 1000, 2)
            result["error"] = f"Request timed out after {response_time_ms}ms"
            result["response_time_ms"] = response_time_ms

        except httpx.RequestError as exc:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            response_time_ms = round(elapsed * 1000, 2)
            result["error"] = f"Request error: {str(exc)}"
            result["response_time_ms"] = response_time_ms

        except Exception as exc:
            result["error"] = f"Unexpected error: {str(exc)}"

        return result

