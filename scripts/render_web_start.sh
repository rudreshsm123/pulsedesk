#!/bin/sh
set -e

# Render's free tier only supports "web" services, not background workers -- so for
# the live demo, the Celery worker and beat processes run alongside the API in this
# one container/service instead of as separate services. docker-compose.yml (the
# local/intended production topology) still runs api/worker/beat as three independent
# services; this script is a free-tier-specific compromise for the deployed demo, not
# a change to the actual architecture.

python -m alembic upgrade head

celery -A app.workers.celery_app worker --loglevel=info --concurrency=2 &
celery -A app.workers.celery_app beat --loglevel=info &

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
