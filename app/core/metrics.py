from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# Deliberately HTTP-only: the API and Celery workers are separate processes, so a
# worker-side Counter would live in memory nobody scrapes. Exposing worker metrics too
# would need a shared backend (e.g. the multiprocess mode, or pushing through Redis),
# which is more infrastructure than a single-process /metrics endpoint justifies here --
# worker task outcomes are already visible via the structured JSON logs each task emits.
http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request latency in seconds", ["method", "path"]
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
