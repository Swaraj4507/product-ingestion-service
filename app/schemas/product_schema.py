from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None)
    active: bool = Field(default=True)


class ProductCreate(ProductBase):
    sku: str = Field(..., min_length=1, max_length=120)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        return value.strip()


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return value.strip()

    def ensure_payload(self) -> "ProductUpdate":
        if self.name is None and self.description is None and self.active is None:
            raise ValueError("At least one field must be provided for update.")
        return self


class ProductOut(BaseModel):
    id: int
    name: str
    sku: str
    description: Optional[str]
    active: bool

    class Config:
        from_attributes = True


class PaginatedProducts(BaseModel):
    total: int
    page: int
    limit: int
    data: list[ProductOut]

