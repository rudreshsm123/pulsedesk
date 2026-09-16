import ssl

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "pulsedesk",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.classify",
        "app.workers.sla_sweep",
        "app.workers.kb_index",
        "app.workers.rag_suggest",
    ],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=5,
)

if settings.redis_url.startswith("rediss://"):
    # Managed Redis over TLS (Upstash, in the live deployment) uses rediss://, which
    # celery's redis backend refuses to start against without an explicit
    # ssl_cert_reqs -- it raises ValueError rather than silently picking a default.
    # CERT_NONE still gets an encrypted connection; it just doesn't verify Upstash's
    # cert against a local CA bundle, which is an accepted tradeoff for connecting to
    # a trusted managed provider from a platform (Render) that may not ship the right
    # CA bundle. Plain redis:// (local Docker Compose) is unaffected.
    _redis_ssl_options = {"ssl_cert_reqs": ssl.CERT_NONE}
    celery_app.conf.broker_use_ssl = _redis_ssl_options
    celery_app.conf.redis_backend_use_ssl = _redis_ssl_options

celery_app.conf.beat_schedule = {
    "sla-sweep-every-minute": {
        "task": "app.workers.sla_sweep.sweep_sla_breaches",
        "schedule": crontab(minute="*"),
    },
}
