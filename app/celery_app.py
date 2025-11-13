from functools import lru_cache

from celery import Celery

from app.core.settings import settings

# Celery configuration
import sys

# Detect Windows platform
is_windows = sys.platform.startswith('win')

@lru_cache(maxsize=1)
def create_celery_app() -> Celery:
    broker_url = settings.celery_broker_url
    result_backend = settings.celery_result_backend or broker_url

    celery = Celery(
        "product_ingestion_service",
        broker=broker_url,
        backend=result_backend,
    )

    celery.conf.update(
        task_default_queue=settings.celery_default_queue,
        task_acks_late=True,
        worker_prefetch_multiplier=settings.celery_prefetch_multiplier,
        worker_pool='solo' if is_windows else 'prefork',
    )

    celery.autodiscover_tasks(["app.service"])

    return celery


celery_app = create_celery_app()
