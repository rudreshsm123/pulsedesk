# Performance experiments

Real numbers, measured against a live Postgres container (`docker compose up`), not
estimated. Reproducible via `scripts/seed_db.py` and `scripts/benchmark_pagination.py`.

## 1. SLA-sweep query: composite index vs sequential scan

`app/workers/sla_sweep.py` runs once a minute and filters tickets by
`status IN (...) AND sla_deadline < now()`. `idx_tickets_sla_sweep` is a composite
index on `(status, priority, sla_deadline)` matching that filter shape.

**Setup**: seeded 100,000 tickets (`python scripts/seed_db.py 100000`) with a
realistic-ish status distribution (90% resolved, small slivers open/breached) so the
query matches ~9% of rows -- an earlier attempt with a uniform random distribution made
~60% of rows match, which is exactly the low-selectivity regime where Postgres
correctly prefers a sequential scan regardless of what indexes exist. Measured with
`EXPLAIN (ANALYZE, BUFFERS)`, worker/beat stopped so the sweep itself couldn't mutate
the seeded rows between the before/after runs.

| | Plan | Execution time |
|---|---|---|
| Before (no index) | `Seq Scan on tickets`, 90,911 rows filtered out | **101.8 ms** |
| After (`idx_tickets_sla_sweep`) | `Bitmap Heap Scan` + `Bitmap Index Scan` | **15.3 ms** |

**~85% reduction (6.6x faster)**, both measured warm-cache (`Buffers: shared hit`, no
disk reads) for a fair comparison. The plan didn't drop to a plain `Index Scan` because
9% of a 100k-row table is still enough rows that Postgres reasonably bitmap-scans the
index then visits heap pages in batch rather than one at a time -- this is the correct
choice, not a missed optimization.

## 2. Pagination: OFFSET/LIMIT vs keyset, at depth

`TicketRepository.list_paginated` uses keyset pagination
(`WHERE (created_at, id) < :cursor`) instead of `OFFSET`, on the reasoning that OFFSET
forces Postgres to generate and discard every row before the target page.

**First measurement, no supporting index** (`scripts/benchmark_pagination.py`, page
2500 of 20-row pages = OFFSET 50,000, 100k-row table):

| | Time |
|---|---|
| OFFSET/LIMIT | 329.3 ms |
| Keyset | 93.7 ms |
| Speedup | 3.5x |

A smaller gap than expected -- because neither query had an index to satisfy
`ORDER BY created_at DESC, id DESC`, so *both* degraded to a full scan + sort. Keyset
pagination's actual performance argument depends on being able to seek directly to the
cursor via an index, not just avoiding `OFFSET`'s row-skipping. Added
`idx_tickets_created_at_id` (migration `0003`) and re-measured:

| Page (of 20 rows) | OFFSET/LIMIT | Keyset | Speedup |
|---|---|---|---|
| 2500 (OFFSET 50,000) | 48.5 ms | 8.2 ms | 5.9x |
| 4900 (OFFSET 98,000, near table end) | 358.2 ms | 41.5 ms | 8.6x |

OFFSET's cost keeps growing with page depth (it still has to generate and discard
everything before the offset); keyset's cost is dominated by the index seek and stays
far flatter. The absolute keyset numbers here (8-42ms) still include noise from cache
locality (different pages of the btree/heap being touched at different depths) rather
than being perfectly O(1) -- reported as measured, not smoothed.

## What wasn't benchmarked here

Connection-pool-size throughput (`pool_size` 5 vs 20 under load) and Celery
worker-process count (1 vs 4) from the original experiment list weren't run --
they need a proper load-generation setup (k6/locust) to produce numbers worth trusting,
which was out of scope for this pass. The two benchmarks above were prioritized because
they're the ones with a concrete, already-shipped code change (an index) to measure
against, not a hypothetical one.
