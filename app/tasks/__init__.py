# Ensure Celery discovers task modules on startup.
from app.tasks import product_tasks  # noqa: F401
from app.tasks import webhook_tasks  # noqa: F401

