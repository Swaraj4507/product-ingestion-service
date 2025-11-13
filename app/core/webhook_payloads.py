from datetime import datetime, timezone
from typing import Any

from app.core.event_types import WebhookEventType


class WebhookPayloadBuilder:
    """Centralized webhook payload builder for consistent payload structure."""

    @staticmethod
    def build_payload_data(event_type: str, **kwargs: Any) -> dict[str, Any]:
        """
        Build payload data for a specific event type based on context.
        This is the single source of truth for all webhook payload data.
        
        Args:
            event_type: The event type (must be from WebhookEventType)
            **kwargs: Event-specific parameters (e.g., total_products, deleted_count)
            
        Returns:
            Event-specific data dictionary for the payload
        """
        if event_type == WebhookEventType.PRODUCT_UPLOAD_COMPLETE.value:
            return {
                "total_products": kwargs.get("total_products", 0),
            }
        
        if event_type == WebhookEventType.BULK_DELETE_COMPLETE.value:
            return {
                "deleted_count": kwargs.get("deleted_count", 0),
            }
        
        return {}

    @staticmethod
    def build_full_payload(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Build complete webhook payload with event_type, timestamp, and data.
        
        Args:
            event_type: The event type
            data: Event-specific data dictionary
            
        Returns:
            Complete webhook payload
        """
        return {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

    @staticmethod
    def get_sample_payload(event_type: str) -> dict[str, Any]:
        """
        Get a sample payload for a given event type for UI/documentation.
        
        Args:
            event_type: The event type
            
        Returns:
            Sample webhook payload
        """
        sample_data = {
            WebhookEventType.PRODUCT_UPLOAD_COMPLETE.value: {"total_products": 500000},
            WebhookEventType.BULK_DELETE_COMPLETE.value: {"deleted_count": 1000000},
        }
        
        data = sample_data.get(event_type, {})
        return WebhookPayloadBuilder.build_full_payload(event_type, data)

