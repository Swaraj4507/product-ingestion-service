from __future__ import annotations

from http import HTTPStatus
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.schemas.product_schema import (
    PaginatedProducts,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)
from app.services.product_service import (
    ProductAlreadyExistsError,
    ProductNotFoundError,
    ProductService,
)

router = APIRouter(prefix="/api/products", tags=["products"])


def get_product_service(session: AsyncSession = Depends(get_async_session)) -> ProductService:
    return ProductService(session)


@router.get("/", response_model=PaginatedProducts)
async def list_products(
    service: ProductService = Depends(get_product_service),
    search: Optional[str] = Query(default=None, min_length=1),
    active: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
) -> PaginatedProducts:
    search_term = search.strip() if search else None
    result = await service.list_products(search=search_term, active=active, page=page, limit=limit)
    return PaginatedProducts(
        total=result.total,
        page=result.page,
        limit=result.limit,
        data=[ProductOut.model_validate(product) for product in result.items],
    )


@router.post(
    "/",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    payload: ProductCreate,
    service: ProductService = Depends(get_product_service),
) -> ProductOut:
    try:
        product = await service.create_product(
            name=payload.name.strip(),
            sku=payload.sku,
            description=payload.description,
            active=payload.active,
        )
    except ProductAlreadyExistsError as exc:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=str(exc)) from exc

    return ProductOut.model_validate(product)


@router.put(
    "/{product_id}",
    response_model=ProductOut,
)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    service: ProductService = Depends(get_product_service),
) -> ProductOut:
    try:
        payload.ensure_payload()
    except ValueError as exc:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)) from exc

    try:
        product = await service.update_product(
            product_id,
            name=payload.name.strip() if payload.name is not None else None,
            description=payload.description,
            active=payload.active,
        )
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc

    return ProductOut.model_validate(product)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_product(
    product_id: UUID,
    service: ProductService = Depends(get_product_service),
) -> dict[str, str]:
    try:
        await service.delete_product(product_id)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc)) from exc

    return {"message": "Deleted successfully"}


@router.delete("/")
async def delete_all_products(
    service: ProductService = Depends(get_product_service),
) -> dict[str, int]:
    deleted = await service.delete_all_products()
    return {"deleted": deleted}

