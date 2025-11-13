from __future__ import annotations

from http import HTTPStatus
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import ServiceContainer, get_container
from app.core.db import get_async_session
from app.schemas.product_schema import (
    PaginatedProducts,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)
from app.schemas.response_schema import ApiResponse
from app.services.product_service import (
    ProductAlreadyExistsError,
    ProductNotFoundError,
    ProductService,
)

router = APIRouter(prefix="/api/products", tags=["products"])


def get_product_service(
    container: ServiceContainer = Depends(get_container),
) -> ProductService:
    return container.product_service


@router.get("", response_model=ApiResponse[PaginatedProducts])
async def list_products(
    service: ProductService = Depends(get_product_service),
    session: AsyncSession = Depends(get_async_session),
    search: Optional[str] = Query(default=None, min_length=1),
    active: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
) -> ApiResponse[PaginatedProducts]:
    search_term = search.strip() if search else None
    result = await service.list_products(session, search=search_term, active=active, page=page, limit=limit)
    paginated_data = PaginatedProducts(
        total=result.total,
        page=result.page,
        limit=result.limit,
        data=[ProductOut.model_validate(product) for product in result.items],
    )
    return ApiResponse(
        message="Products retrieved successfully",
        results=paginated_data,
    )


@router.post(
    "",
    response_model=ApiResponse[ProductOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    payload: ProductCreate,
    override: bool = Query(default=False, description="Override existing product with same SKU"),
    service: ProductService = Depends(get_product_service),
    session: AsyncSession = Depends(get_async_session),
) -> ApiResponse[ProductOut]:
    try:
        product = await service.create_product(
            session,
            name=payload.name.strip(),
            sku=payload.sku,
            description=payload.description,
            active=payload.active,
            override=override,
        )
        message = "Product updated successfully" if override else "Product created successfully"
    except ProductAlreadyExistsError as exc:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=str(exc)) from exc

    return ApiResponse(
        message=message,
        results=ProductOut.model_validate(product),
    )


@router.put(
    "/{product_id}",
    response_model=ApiResponse[ProductOut],
)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    override: bool = Query(default=False, description="Override existing product with same SKU"),
    service: ProductService = Depends(get_product_service),
    session: AsyncSession = Depends(get_async_session),
) -> ApiResponse[ProductOut]:
    try:
        payload.ensure_payload()
    except ValueError as exc:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)) from exc

    try:
        product = await service.update_product(
            session,
            product_id,
            name=payload.name.strip() if payload.name is not None else None,
            description=payload.description,
            active=payload.active,
            sku=payload.sku.strip() if payload.sku is not None else None,
            override=override,
        )
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc
    except ProductAlreadyExistsError as exc:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=str(exc)) from exc

    return ApiResponse(
        message="Product updated successfully",
        results=ProductOut.model_validate(product),
    )


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_product(
    product_id: UUID,
    service: ProductService = Depends(get_product_service),
    session: AsyncSession = Depends(get_async_session),
) -> ApiResponse[dict[str, str]]:
    try:
        await service.delete_product(session, product_id)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc

    return ApiResponse(
        message="Product deleted successfully",
        results={"id": str(product_id)},
    )


@router.post("/bulk-delete", status_code=status.HTTP_202_ACCEPTED)
async def bulk_delete_products(
    confirm: bool = Query(default=False, description="Confirmation required to proceed"),
    service: ProductService = Depends(get_product_service),
    session: AsyncSession = Depends(get_async_session),
    container: ServiceContainer = Depends(get_container),
) -> ApiResponse[dict[str, str]]:
    if not confirm:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Confirmation required. Append ?confirm=true to proceed.",
        )

    task_id = await service.trigger_bulk_delete(session, container.celery_app)
    return ApiResponse(
        message="Bulk delete started",
        results={"task_id": str(task_id)},
    )

