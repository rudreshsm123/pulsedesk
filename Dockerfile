# Pinned to 3.12, not the 3.14 used in local dev: production images should sit on a
# Python release with a mature wheel/base-image ecosystem, not the newest release --
# the app itself uses no 3.13+/3.14-only syntax, so this costs nothing.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# Separate build stage so gcc/build headers (needed only if a dependency has no
# prebuilt wheel for this platform) never end up in the final image.
FROM base AS builder
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

FROM base AS runtime
RUN useradd --create-home --uid 1000 appuser
COPY --from=builder /install /usr/local
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
# celery beat writes its schedule file into the working directory at runtime, so /app
# needs to be writable by the user the process actually runs as, not just readable.
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
