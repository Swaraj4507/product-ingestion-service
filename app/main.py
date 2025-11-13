from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.products import router as product_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.upload import router as upload_router
from app.api.routes.webhooks import router as webhooks_router
from app.core.container import get_container


def create_application() -> FastAPI:
    container = get_container()
    application = FastAPI(
        title=container.settings.app_name,
        version=container.settings.version,
    )
    application.state.container = container
    application.include_router(health_router)
    application.include_router(upload_router)
    application.include_router(product_router)
    application.include_router(tasks_router)
    application.include_router(webhooks_router)
    return application


app = create_application()
