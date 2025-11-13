from collections.abc import Iterable
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.product import Product


class ProductRepository:
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

