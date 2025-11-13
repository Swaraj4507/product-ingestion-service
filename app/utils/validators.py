from app.core.event_types import WebhookEventType


def validate_webhook_url(url: str) -> str:
    """Validate webhook URL format."""
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")
    return url.strip()


def validate_webhook_event_type(event_type: str) -> str:
    """Validate webhook event type."""
    if not WebhookEventType.is_valid(event_type):
        valid_types = ", ".join(WebhookEventType.all())
        raise ValueError(f"Invalid event type. Valid types are: {valid_types}")
    return event_type.strip()


def validate_optional_webhook_url(url: str | None) -> str | None:
    """Validate optional webhook URL format."""
    if url is None:
        return url
    return validate_webhook_url(url)


def validate_optional_webhook_event_type(event_type: str | None) -> str | None:
    """Validate optional webhook event type."""
    if event_type is None:
        return event_type
    return validate_webhook_event_type(event_type)

