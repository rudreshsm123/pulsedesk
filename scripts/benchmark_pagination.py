"""Compares OFFSET-based vs keyset pagination at a deep page, against the table seeded
by scripts/seed_db.py. Run after seeding at least ~100k rows for a visible difference.
"""

import asyncio
import time

import asyncpg

from app.core.config import get_settings

PAGE_SIZE = 20
DEEP_PAGE_NUMBER = 2500  # i.e. OFFSET 50,000


def _asyncpg_dsn(sqlalchemy_url: str) -> str:
    return sqlalchemy_url.replace("postgresql+asyncpg://", "postgresql://")


async def main() -> None:
    settings = get_settings()
    conn = await asyncpg.connect(_asyncpg_dsn(settings.database_url))

    offset_value = DEEP_PAGE_NUMBER * PAGE_SIZE
    start = time.perf_counter()
    await conn.fetch(
        "SELECT * FROM tickets ORDER BY created_at DESC, id DESC LIMIT $1 OFFSET $2",
        PAGE_SIZE,
        offset_value,
    )
    offset_ms = (time.perf_counter() - start) * 1000

    # The keyset cursor for "page 2500" -- find the (created_at, id) of the row right
    # before it once, the same way TicketService.list_tickets would build a cursor from
    # the previous page's last row, then benchmark the seek itself.
    cursor_row = await conn.fetchrow(
        "SELECT created_at, id FROM tickets ORDER BY created_at DESC, id DESC "
        "LIMIT 1 OFFSET $1",
        offset_value - 1,
    )
    start = time.perf_counter()
    await conn.fetch(
        "SELECT * FROM tickets WHERE (created_at, id) < ($1, $2) "
        "ORDER BY created_at DESC, id DESC LIMIT $3",
        cursor_row["created_at"],
        cursor_row["id"],
        PAGE_SIZE,
    )
    keyset_ms = (time.perf_counter() - start) * 1000

    print(f"Page {DEEP_PAGE_NUMBER} (OFFSET {offset_value}), {PAGE_SIZE} rows/page:")
    print(f"  OFFSET/LIMIT : {offset_ms:.2f} ms")
    print(f"  keyset       : {keyset_ms:.2f} ms")
    print(f"  speedup      : {offset_ms / keyset_ms:.1f}x")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
