import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import get_logger, request_id_ctx

logger = get_logger("pulsedesk.access")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Binds a request ID to every log line emitted while handling this request,
    and echoes it back so a client/agent worker can correlate a failure across
    the API -> Celery -> LLM call chain."""

    async def dispatch(self, request: Request, call_next):
        incoming_id = request.headers.get("X-Request-ID")
        request_id = incoming_id or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            response.headers["X-Request-ID"] = request_id
            logger.info(
                f"{request.method} {request.url.path} {response.status_code} {duration_ms:.1f}ms"
            )
            return response
        finally:
            request_id_ctx.reset(token)
