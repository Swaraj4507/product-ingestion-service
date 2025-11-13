from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.utils.validators import (
    validate_optional_webhook_event_type,
    validate_optional_webhook_url,
    validate_webhook_event_type,
    validate_webhook_url,
)


class WebhookBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1, max_length=64)
    is_active: bool = Field(default=True)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return validate_webhook_url(value)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        return validate_webhook_event_type(value)


class WebhookCreate(WebhookBase):
    pass


class WebhookUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    url: Optional[str] = Field(default=None, min_length=1)
    event_type: Optional[str] = Field(default=None, min_length=1, max_length=64)
    is_active: Optional[bool] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: Optional[str]) -> Optional[str]:
        return validate_optional_webhook_url(value)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: Optional[str]) -> Optional[str]:
        return validate_optional_webhook_event_type(value)

    def ensure_payload(self) -> "WebhookUpdate":
        if self.name is None and self.url is None and self.event_type is None and self.is_active is None:
            raise ValueError("At least one field must be provided for update.")
        return self


class WebhookOut(BaseModel):
    id: UUID
    name: str
    url: str
    event_type: str
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

