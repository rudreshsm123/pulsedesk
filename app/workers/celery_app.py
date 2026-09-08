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

celery_app.conf.beat_schedule = {
    "sla-sweep-every-minute": {
        "task": "app.workers.sla_sweep.sweep_sla_breaches",
        "schedule": crontab(minute="*"),
    },
}
