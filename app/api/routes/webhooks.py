from http import HTTPStatus
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.schemas.response_schema import ApiResponse
from app.schemas.webhook_schema import WebhookCreate, WebhookOut, WebhookUpdate
from app.services.webhook_service import WebhookNotFoundError, WebhookService

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def get_webhook_service(session: AsyncSession = Depends(get_async_session)) -> WebhookService:
    return WebhookService(session)


@router.get("/events", response_model=ApiResponse[list[dict[str, str]]])
async def list_event_types(
    service: WebhookService = Depends(get_webhook_service),
) -> ApiResponse[list[dict[str, str]]]:
    events = service.get_event_types()
    return ApiResponse(
        message="Event types retrieved successfully",
        results=events,
    )


@router.get("/payloads", response_model=ApiResponse[dict[str, dict[str, Any]]])
async def get_sample_payloads(
    event_type: Optional[str] = Query(default=None, min_length=1),
    service: WebhookService = Depends(get_webhook_service),
) -> ApiResponse[dict[str, dict[str, Any]]]:
    payloads = service.get_sample_payloads(event_type=event_type)
    return ApiResponse(
        message="Sample payloads retrieved successfully",
        results=payloads,
    )


@router.get("", response_model=ApiResponse[list[WebhookOut]])
async def list_webhooks(
    service: WebhookService = Depends(get_webhook_service),
    event_type: Optional[str] = Query(default=None, min_length=1),
    is_active: Optional[bool] = Query(default=None),
) -> ApiResponse[list[dict]]:
    webhooks = await service.list_webhooks(event_type=event_type, is_active=is_active)
    return ApiResponse(
        message="Webhooks retrieved successfully",
        results=webhooks,
    )


@router.post(
    "",
    response_model=ApiResponse[WebhookOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_webhook(
    payload: WebhookCreate,
    service: WebhookService = Depends(get_webhook_service),
) -> ApiResponse[dict]:
    webhook = await service.create_webhook(
        name=payload.name.strip(),
        url=payload.url,
        event_type=payload.event_type.strip(),
        is_active=payload.is_active,
    )
    return ApiResponse(
        message="Webhook created successfully",
        results=webhook,
    )


@router.get(
    "/{webhook_id}",
    response_model=ApiResponse[WebhookOut],
)
async def get_webhook(
    webhook_id: UUID,
    service: WebhookService = Depends(get_webhook_service),
) -> ApiResponse[dict]:
    try:
        webhook = await service.get_webhook(webhook_id)
    except WebhookNotFoundError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc

    return ApiResponse(
        message="Webhook retrieved successfully",
        results=webhook,
    )


@router.put(
    "/{webhook_id}",
    response_model=ApiResponse[WebhookOut],
)
async def update_webhook(
    webhook_id: UUID,
    payload: WebhookUpdate,
    service: WebhookService = Depends(get_webhook_service),
) -> ApiResponse[dict]:
    try:
        payload.ensure_payload()
    except ValueError as exc:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)) from exc

    try:
        webhook = await service.update_webhook(
            webhook_id,
            name=payload.name.strip() if payload.name is not None else None,
            url=payload.url,
            event_type=payload.event_type.strip() if payload.event_type is not None else None,
            is_active=payload.is_active,
        )
    except WebhookNotFoundError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc

    return ApiResponse(
        message="Webhook updated successfully",
        results=webhook,
    )


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_webhook(
    webhook_id: UUID,
    service: WebhookService = Depends(get_webhook_service),
) -> ApiResponse[dict[str, str]]:
    try:
        await service.delete_webhook(webhook_id)
    except WebhookNotFoundError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc

    return ApiResponse(
        message="Webhook deleted successfully",
        results={"id": str(webhook_id)},
    )


@router.post(
    "/{webhook_id}/test",
    status_code=status.HTTP_200_OK,
)
async def test_webhook(
    webhook_id: UUID,
    custom_payload: Optional[dict[str, Any]] = Body(default=None, description="Optional custom payload to send"),
    service: WebhookService = Depends(get_webhook_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        result = await service.test_webhook(webhook_id, custom_payload=custom_payload)
    except WebhookNotFoundError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)) from exc

    return ApiResponse(
        message="Webhook test completed",
        results=result,
    )

