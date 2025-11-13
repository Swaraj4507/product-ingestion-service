from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.upload import TaskType
from app.repository.product_repository import ProductRepository
from app.repository.upload_repository import UploadRepository


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
    def __init__(self) -> None:
        """ProductService is a singleton - session is passed per request."""
        pass

    async def list_products(
        self,
        session: AsyncSession,
        *,
        search: Optional[str],
        active: Optional[bool],
        page: int,
        limit: int,
    ) -> ProductListResult:
        page = max(page, 1)
        limit = max(min(limit, 100), 1)

        repository = ProductRepository(session)
        items, total = await repository.list_products(
            search=search,
            active=active,
            page=page,
            limit=limit,
        )

        return ProductListResult(total=total, page=page, limit=limit, items=items)

    async def create_product(
        self,
        session: AsyncSession,
        *,
        name: str,
        sku: str,
        description: Optional[str],
        active: bool,
        override: bool = False,
    ) -> Product:
        repository = ProductRepository(session)
        existing_product = await repository.find_by_sku(sku)

        if existing_product:
            if not override:
                raise ProductAlreadyExistsError(f"Product with SKU '{sku}' already exists.")
            # Override: update existing product
            existing_product.name = name
            existing_product.description = description
            existing_product.active = active
            return await repository.update(existing_product)

        # Create new product
        normalized_sku = sku.strip().lower()
        product = Product(
            name=name,
            sku=normalized_sku,
            description=description,
            active=active,
        )
        return await repository.create(product)

    async def update_product(
        self,
        session: AsyncSession,
        product_id: UUID,
        *,
        name: Optional[str],
        sku: Optional[str],
        description: Optional[str],
        active: Optional[bool],
        override: bool = False,
    ) -> Product:
        repository = ProductRepository(session)
        product = await repository.find_by_id(product_id)
        if not product:
            raise ProductNotFoundError(f"Product with id {product_id} not found.")

        if name is not None:
            product.name = name
        if description is not None:
            product.description = description
        if active is not None:
            product.active = active
        
        if sku is not None:
            normalized_sku = sku.strip().lower()
            # Check if SKU already exists on a different product
            if product.sku.lower() != normalized_sku:
                existing_product = await repository.find_by_sku_excluding_id(sku, product_id)
                
                if existing_product:
                    if not override:
                        raise ProductAlreadyExistsError(
                            f"Product with SKU '{sku}' already exists. Use override=true to update."
                        )
                    # Override: delete the conflicting product
                    await repository.delete(existing_product)
            
            # Update current product's SKU
            product.sku = normalized_sku

        return await repository.update(product)

    async def delete_product(self, session: AsyncSession, product_id: UUID) -> None:
        repository = ProductRepository(session)
        product = await repository.find_by_id(product_id)
        if not product:
            raise ProductNotFoundError(f"Product with id {product_id} not found.")

        await repository.delete(product)

    async def delete_all_products(self, session: AsyncSession) -> int:
        try:
            repository = ProductRepository(session)
            return await repository.delete_all()
        except IntegrityError as exc:  # pragma: no cover - defensive
            raise ValueError("Failed to delete products due to constraint violation.") from exc

    async def trigger_bulk_delete(self, session: AsyncSession, celery_app) -> UUID:
        """Trigger bulk delete task. celery_app is passed from container to avoid circular import."""
        task_id = uuid4()
        upload_repo = UploadRepository(session)
        await upload_repo.create_upload(
            task_id=task_id,
            filename="BULK_DELETE",
            task_type=TaskType.BULK_DELETE,
        )
        await session.commit()

        celery_app.send_task(
            "app.tasks.product_tasks.bulk_delete_products",
            args=[str(task_id)],
        )

        return task_id

