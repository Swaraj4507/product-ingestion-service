from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.webhook import Webhook


class WebhookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_webhook(
        self,
        *,
        name: str,
        url: str,
        event_type: str,
        is_active: bool,
    ) -> Webhook:
        webhook = Webhook(
            name=name,
            url=url,
            event_type=event_type,
            is_active=is_active,
        )
        self._session.add(webhook)
        await self._session.flush()
        await self._session.refresh(webhook)
        return webhook

    async def get_by_id(self, webhook_id: UUID) -> Optional[Webhook]:
        stmt = select(Webhook).where(Webhook.id == webhook_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_webhooks(
        self,
        *,
        event_type: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> list[Webhook]:
        stmt = select(Webhook)

        if event_type:
            stmt = stmt.where(Webhook.event_type == event_type)

        if is_active is not None:
            stmt = stmt.where(Webhook.is_active == is_active)

        stmt = stmt.order_by(Webhook.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_by_event_type(self, event_type: str) -> list[Webhook]:
        stmt = (
            select(Webhook)
            .where(Webhook.event_type == event_type)
            .where(Webhook.is_active == True)
            .order_by(Webhook.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_webhook(
        self,
        webhook: Webhook,
        *,
        name: Optional[str],
        url: Optional[str],
        event_type: Optional[str],
        is_active: Optional[bool],
    ) -> Webhook:
        if name is not None:
            webhook.name = name
        if url is not None:
            webhook.url = url
        if event_type is not None:
            webhook.event_type = event_type
        if is_active is not None:
            webhook.is_active = is_active

        await self._session.flush()
        await self._session.refresh(webhook)
        return webhook

    async def delete_webhook(self, webhook: Webhook) -> None:
        await self._session.delete(webhook)
        await self._session.flush()


class WebhookSyncRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, webhook_id: UUID) -> Optional[Webhook]:
        return self._session.query(Webhook).filter(Webhook.id == webhook_id).first()

    def get_active_by_event_type(self, event_type: str) -> list[Webhook]:
        return (
            self._session.query(Webhook)
            .filter(Webhook.event_type == event_type)
            .filter(Webhook.is_active == True)
            .order_by(Webhook.created_at)
            .all()
        )

