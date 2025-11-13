from celery import shared_task

from app.core.container import get_container


@shared_task(name="app.service.echo")
def echo(message: str) -> str:
    container = get_container()
    return f"{container.settings.app_name}: {message}"


