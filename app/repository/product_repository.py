from collections.abc import Iterable
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.product import Product


class ProductRepository:
    """Async repository for product operations (used in services)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_sku(self, sku: str) -> Optional[Product]:
        """Find a product by SKU (case-insensitive)."""
        normalized_sku = sku.strip().lower()
        stmt = select(Product).where(func.lower(Product.sku) == normalized_sku)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_id(self, product_id: UUID) -> Optional[Product]:
        """Find a product by ID."""
        return await self._session.get(Product, product_id)

    async def find_by_sku_excluding_id(self, sku: str, exclude_id: UUID) -> Optional[Product]:
        """Find a product by SKU excluding a specific ID."""
        normalized_sku = sku.strip().lower()
        stmt = select(Product).where(
            func.lower(Product.sku) == normalized_sku,
            Product.id != exclude_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_products(
        self,
        *,
        search: Optional[str] = None,
        active: Optional[bool] = None,
        page: int,
        limit: int,
    ) -> tuple[list[Product], int]:
        """List products with filtering and pagination."""
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
        items = list(rows.scalars().all())

        return items, total

    async def create(self, product: Product) -> Product:
        """Create a new product."""
        self._session.add(product)
        await self._session.flush()
        return product

    async def update(self, product: Product) -> Product:
        """Update an existing product."""
        await self._session.flush()
        await self._session.refresh(product)
        return product

    async def delete(self, product: Product) -> None:
        """Delete a product."""
        await self._session.delete(product)
        await self._session.flush()

    async def delete_all(self) -> int:
        """Delete all products."""
        result = await self._session.execute(delete(Product))
        return result.rowcount or 0


class ProductSyncRepository:
    """Sync repository for product operations (used in Celery tasks)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, products: Iterable[dict[str, Any]]) -> int:
        deduped: dict[str, dict[str, Any]] = {}
        for product in products:
            normalized = dict(product)
            sku = normalized.get("sku", "")
            normalized["sku"] = sku.lower()
            deduped[normalized["sku"]] = normalized

        if not deduped:
            return 0

        payload = list(deduped.values())

        stmt = insert(Product).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=[func.lower(Product.sku)],
            set_={
                "name": stmt.excluded.name,
                "description": stmt.excluded.description,
                "active": stmt.excluded.active,
                "updated_at": func.now(),
            },
        )

        result = self._session.execute(stmt)
        return result.rowcount or len(payload)

    def count_all(self) -> int:
        stmt = select(func.count(Product.id))
        result = self._session.execute(stmt)
        return result.scalar_one() or 0

    def delete_chunk(self, limit: int) -> int:
        subquery = select(Product.id).limit(limit).subquery()
        delete_stmt = delete(Product).where(Product.id.in_(select(subquery.c.id)))
        result = self._session.execute(delete_stmt)
        return result.rowcount or 0

