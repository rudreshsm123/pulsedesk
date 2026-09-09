# PulseDesk

AI-augmented support ticket triage and resolution platform. Tickets are ingested
asynchronously, classified by category/priority, matched against a knowledge base via
RAG for a draft resolution, and monitored for SLA breaches — all behind a
role-scoped (customer/agent/admin) REST API.

## Problem

Support teams drown in tickets; agents waste time guessing priority and searching
documentation before replying. PulseDesk automates the triage step (classification +
a grounded, source-attributed draft reply) while keeping a human in the loop — the AI
never auto-replies to a customer.

## Architecture

```
                    Client (customer/agent/admin)
                              |  HTTPS + JWT
                              v
                        FastAPI (async)
                    /                    \
                   v                      v
            PostgreSQL              Redis (broker,
            + pgvector              rate limiting)
                                          |
                                          v
                                  Celery worker(s)
                                  - classify ticket
                                  - RAG suggestion
                                  - SLA sweep (beat)
```

Ticket lifecycle: `POST /tickets` writes the row (`PENDING`) and returns immediately
(`202 Accepted`) with the classification enqueued to Celery, not run inline. The
classify task tags category/priority, then chains into a RAG task that embeds the
ticket, retrieves the nearest KB chunks via pgvector, and stores a grounded draft reply
with source article IDs. A `beat`-scheduled sweep flags any ticket whose SLA deadline
has passed as `BREACHED`.

## Tech stack, and why

| Choice | Why |
|---|---|
| **FastAPI + async SQLAlchemy** | The app is I/O-bound (DB, Redis, LLM calls) — an event loop handles many concurrent requests without the GIL contention threading would add here. |
| **PostgreSQL + pgvector** | Tickets/users/KB articles are relational with real integrity constraints (idempotency uniqueness, FK cascades) — a second vector database would be complexity for its own sake at this data scale, when pgvector gives RAG support on the same instance. |
| **Redis + Celery** | Ticket classification and RAG generation are too slow to run inside the request; Celery also backs the rate limiter's token buckets. |
| **HNSW over ivfflat** for the KB embedding index | See "bugs found," below — ivfflat trains its clusters at index-creation time and silently returns near-zero recall until it's been rebuilt against a non-trivial amount of data; HNSW builds incrementally and is correct from the first inserted row. |
| **A swappable `LLMProvider` interface, mock by default** | No LLM API key was available while building this. Classification and resolution-drafting are behind `app/services/llm/`, with a deterministic, zero-cost implementation (rule-based classification; extractive-only, threshold-gated resolution drafting) that's structurally incapable of hallucinating, since it never generates text beyond what's in the retrieved KB chunk. Swapping in a real provider is a matter of implementing the same interface. |
| **PyJWT, not python-jose** | `pip-audit` flagged `ecdsa` (a python-jose dependency with no available fix) as vulnerable; since the app only signs with HS256, PyJWT was a strictly better choice, not a suppressed finding. |
| **Keyset pagination, not OFFSET** | Measured, not assumed — see `docs/performance.md`. |

## What's deliberately not here

- **A real LLM call.** Wired up as an interface (`app/services/llm/base.py`) with a
  provider selectable via `LLM_PROVIDER`; only `mock` is implemented, since no API key
  was available. The mock is extractive-only and threshold-gated specifically so this
  isn't a "pretend it works" stub — it produces genuinely grounded output or an honest
  "not enough information," never a fabricated answer.
- **A dedicated vector database (Pinecone/Weaviate).** pgvector on the existing
  Postgres instance is the right-sized choice at this data volume.
- **Kafka, microservices, Kubernetes.** Redis+Celery already demonstrates queueing;
  Docker Compose already demonstrates containerization. Reaching for more here would
  move effort toward infrastructure this project's scale doesn't need, not toward
  provable engineering depth.
- **Cloud deployment.** Render/Railway/Supabase need account-specific secrets this
  environment doesn't have; the app is deployment-ready (stateless API, migration job,
  externalized config) but actually deploying it is a manual step.
- **File uploads, connection-pool/worker-concurrency load testing.** See
  `docs/security.md` and `docs/performance.md` for why.

## Running it

```bash
cp .env.example .env          # override JWT_SECRET_KEY etc. for anything beyond local dev
docker compose up -d --build
```

This starts Postgres (with pgvector), Redis, runs migrations once (`migrate` service),
then starts the API (`:8000`), a Celery worker, and Celery beat. Interactive API docs:
`http://localhost:8000/docs`.

### Local dev without Docker

```bash
pip install -r requirements-dev.txt
docker compose up -d postgres redis   # still need these two
alembic upgrade head
uvicorn app.main:app --reload
celery -A app.workers.celery_app worker --loglevel=info   # separate terminal
celery -A app.workers.celery_app beat --loglevel=info     # separate terminal
```

### Tests

```bash
pytest                 # unit + API tests (no DB needed) + integration tests
                        # (Testcontainers spins up its own ephemeral Postgres)
ruff check .            # lint
```

67 tests: unit tests mock out the DB via fakes (`tests/fakes.py`); integration tests
run against a real, ephemeral Postgres+pgvector container per test session, not mocks
— see `docs/security.md` for the mock-vs-real rationale.

## API surface

Versioned under `/api/v1`. Full schema at `/docs` once running; representative
endpoints:

| Endpoint | Auth | Notes |
|---|---|---|
| `POST /auth/register`, `/auth/login`, `/auth/refresh` | — | Public signup always creates a `customer`; agent/admin accounts are provisioned out-of-band. |
| `POST /tickets` | customer | Requires `Idempotency-Key`; returns `202` immediately, classification runs async. |
| `GET /tickets` | any | RBAC-scoped server-side: customers see only their own tickets. |
| `GET /tickets/{id}/ai-suggestion` | agent/admin | `200` with the grounded draft + source article IDs, or `202` while still generating. |
| `PATCH /tickets/{id}/assign` | agent/admin | `409` if the ticket is already resolved/breached. |
| `POST /kb-articles` | admin | Triggers async chunking + embedding. |
| `GET /health`, `GET /metrics` | — | Liveness + Prometheus-format metrics. |

## Performance

See [`docs/performance.md`](docs/performance.md) for real `EXPLAIN ANALYZE` numbers
(measured against a 100k-row seeded table, not estimated):

- SLA-sweep query: **101.8ms → 15.3ms** (~85% faster) after adding a composite index.
- Deep-page pagination: **358.2ms → 41.5ms** (8.6x) for keyset vs. OFFSET at page 4900.

## Security

See [`docs/security.md`](docs/security.md): auth/authorization design, prompt-injection
handling for the RAG pipeline, and what's explicitly out of scope.

## Bugs found by actually running this, not just writing it

Two of the more interesting ones (full details in the relevant commits):

1. **Cross-event-loop connection reuse.** Celery tasks call `asyncio.run()` per
   invocation, creating a new event loop each time, but the SQLAlchemy engine's
   connection pool is a process-wide singleton whose connections are bound to whichever
   loop created them — reusing one from a dead loop raised `RuntimeError: Event loop is
   closed`. Fixed by disposing the pool at the end of each task while its loop is still
   alive (`app/workers/task_runner.py`).
2. **ivfflat trained on an empty table.** The KB embedding index was created before any
   articles existed; ivfflat's k-means clustering on zero rows made similarity search
   silently return zero matches for a newly indexed article, so every RAG suggestion
   fell back to "not enough information" regardless of how well a ticket actually
   matched the knowledge base. Fixed by switching to HNSW, which builds incrementally
   and needs no training phase (migration `0002`).
