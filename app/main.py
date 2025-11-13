from fastapi import FastAPI

from app.core.container import get_container
from app.routes.health import router as health_router


def create_application() -> FastAPI:
    container = get_container()
    application = FastAPI(
        title=container.settings.app_name,
        version=container.settings.version,
    )
    application.state.container = container
    application.include_router(health_router)
    return application


app = create_application()
