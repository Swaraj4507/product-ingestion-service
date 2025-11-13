from enum import Enum


class WebhookEventType(str, Enum):
    """Centralized webhook event types."""

    PRODUCT_UPLOAD_COMPLETE = "product_upload_complete"
    BULK_DELETE_COMPLETE = "bulk_delete_complete"

    @classmethod
    def all(cls) -> list[str]:
        """Return all available event types as a list."""
        return [event.value for event in cls]

    @classmethod
    def is_valid(cls, event_type: str) -> bool:
        """Check if an event type is valid."""
        return event_type in cls.all()


