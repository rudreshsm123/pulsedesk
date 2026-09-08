from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.core.config import get_settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware

settings = get_settings()

configure_logging()

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(RequestIdMiddleware)
register_exception_handlers(app)

app.include_router(health_router, prefix="/api/v1")
