"""Seeds a large ticket table for the performance benchmarks in docs/performance.md.

Uses asyncpg's COPY protocol directly (not the ORM) because inserting 100k+ rows one at
a time through SQLAlchemy would itself take minutes and isn't what's being measured --
this script's job is just to get representative data into the table quickly.

Usage: python scripts/seed_db.py [num_tickets]
"""

import asyncio
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg

from app.core.config import get_settings

STATUSES = ["PENDING", "CLASSIFIED", "IN_PROGRESS", "RESOLVED", "BREACHED"]
PRIORITIES = ["LOW", "MEDIUM", "HIGH", "URGENT"]
CATEGORIES = ["billing", "technical", "account", "general"]


def _asyncpg_dsn(sqlalchemy_url: str) -> str:
    return sqlalchemy_url.replace("postgresql+asyncpg://", "postgresql://")


async def seed(num_tickets: int) -> None:
    settings = get_settings()
    conn = await asyncpg.connect(_asyncpg_dsn(settings.database_url))

    customer_id = uuid.uuid4()
    await conn.execute(
        "INSERT INTO users (id, email, hashed_password, role) VALUES ($1, $2, $3, 'customer') "
        "ON CONFLICT DO NOTHING",
        customer_id,
        f"seed-customer-{customer_id}@example.com",
        "x",
    )

    now = datetime.now(UTC)
    rows = []
    for i in range(num_tickets):
        created_at = now - timedelta(minutes=i)
        # Realistic-ish distribution: most support tickets end up resolved, and among
        # the ones still open, most are within their SLA window -- only a small sliver
        # are actually breached. A uniform distribution (as an earlier version of this
        # script used) makes ~60% of rows match the SLA-sweep filter, which is exactly
        # the low-selectivity case where Postgres correctly prefers a sequential scan
        # over the index -- realistic data is what makes the index's benefit visible.
        # weights align with STATUSES: PENDING/CLASSIFIED/IN_PROGRESS/RESOLVED/BREACHED
        status = random.choices(STATUSES, weights=[3, 3, 3, 90, 1], k=1)[0]
        if status in ("PENDING", "CLASSIFIED", "IN_PROGRESS"):
            sla_offset = random.choices(
                [timedelta(hours=-2), timedelta(hours=24)], weights=[1, 9], k=1
            )[0]
        else:
            sla_offset = timedelta(hours=24)
        rows.append(
            (
                uuid.uuid4(),
                customer_id,
                None,
                f"Seeded ticket {i}",
                "Seeded body text for benchmarking.",
                status,
                random.choice(CATEGORIES),
                random.choice(PRIORITIES),
                None,
                None,
                created_at + sla_offset,
                created_at,
                created_at,
            )
        )

    await conn.copy_records_to_table(
        "tickets",
        records=rows,
        columns=[
            "id",
            "customer_id",
            "assigned_agent_id",
            "subject",
            "body",
            "status",
            "category",
            "priority",
            "ai_confidence",
            "idempotency_key",
            "sla_deadline",
            "created_at",
            "updated_at",
        ],
    )
    await conn.close()
    print(f"Seeded {num_tickets} tickets for customer {customer_id}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
    asyncio.run(seed(n))
