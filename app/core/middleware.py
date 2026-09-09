import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import get_logger, request_id_ctx
from app.core.metrics import http_request_duration_seconds, http_requests_total

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
            duration = time.perf_counter() - start
            response.headers["X-Request-ID"] = request_id

            # Prefer the matched route's path template (e.g. "/tickets/{ticket_id}") over
            # the raw URL so per-ticket-ID paths don't each become their own metric label
            # -- an unbounded label is a Prometheus cardinality leak.
            route = request.scope.get("route")
            path_label = route.path if route is not None else request.url.path
            http_requests_total.labels(request.method, path_label, response.status_code).inc()
            http_request_duration_seconds.labels(request.method, path_label).observe(duration)

            logger.info(
                f"{request.method} {request.url.path} {response.status_code} "
                f"{duration * 1000:.1f}ms"
            )
            return response
        finally:
            request_id_ctx.reset(token)
