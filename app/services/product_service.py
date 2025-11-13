from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.product import Product


class ProductNotFoundError(LookupError):
    """Raised when a product could not be located."""


class ProductAlreadyExistsError(ValueError):
    """Raised when attempting to create a duplicate product."""


@dataclass(frozen=True)
class ProductListResult:
    total: int
    page: int
    limit: int
    items: list[Product]


class ProductService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_products(
        self,
        *,
        search: Optional[str],
        active: Optional[bool],
        page: int,
        limit: int,
    ) -> ProductListResult:
        page = max(page, 1)
        limit = max(min(limit, 100), 1)

        filters = []
        if search:
            pattern = f"%{search.lower()}%"
            filters.append(
                or_(
                    func.lower(Product.name).like(pattern),
                    func.lower(Product.sku).like(pattern),
                    func.lower(Product.description).like(pattern),
                )
            )

        if active is not None:
            filters.append(Product.active == active)

        base_query = select(Product)
        count_query = select(func.count()).select_from(Product)

        if filters:
            for condition in filters:
                base_query = base_query.where(condition)
                count_query = count_query.where(condition)

        total_result = await self._session.execute(count_query)
        total = int(total_result.scalar() or 0)

        offset_value = (page - 1) * limit
        base_query = base_query.order_by(Product.id).offset(offset_value).limit(limit)
        rows = await self._session.execute(base_query)
        items = rows.scalars().all()

        return ProductListResult(total=total, page=page, limit=limit, items=list(items))

    async def create_product(
        self,
        *,
        name: str,
        sku: str,
        description: Optional[str],
        active: bool,
    ) -> Product:
        normalized_sku = sku.strip().lower()
        exists_query = select(func.count()).select_from(Product).where(
            func.lower(Product.sku) == normalized_sku
        )
        exists_result = await self._session.execute(exists_query)
        if (exists_result.scalar() or 0) > 0:
            raise ProductAlreadyExistsError(f"Product with SKU '{sku}' already exists.")

        product = Product(
            name=name,
            sku=normalized_sku,
            description=description,
            active=active,
        )
        self._session.add(product)
        await self._session.flush()
        return product

    async def update_product(
        self,
        product_id: UUID,
        *,
        name: Optional[str],
        description: Optional[str],
        active: Optional[bool],
    ) -> Product:
        product = await self._session.get(Product, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with id {product_id} not found.")

        if name is not None:
            product.name = name
        if description is not None:
            product.description = description
        if active is not None:
            product.active = active

        await self._session.flush()
        await self._session.refresh(product)
        return product

    async def delete_product(self, product_id: UUID) -> None:
        product = await self._session.get(Product, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with id {product_id} not found.")

        await self._session.delete(product)
        await self._session.flush()

    async def delete_all_products(self) -> int:
        try:
            result = await self._session.execute(delete(Product))
            deleted = result.rowcount or 0
            return int(deleted)
        except IntegrityError as exc:  # pragma: no cover - defensive
            raise ValueError("Failed to delete products due to constraint violation.") from exc

