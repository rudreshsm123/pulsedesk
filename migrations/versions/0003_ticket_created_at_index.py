"""add index supporting created_at/id keyset pagination on tickets

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-09

Keyset pagination's whole performance argument versus OFFSET/LIMIT is that it can seek
directly to a cursor position instead of scanning-then-skipping -- but that seek needs
an index in the same order the query sorts by. Without this index, benchmarking showed
keyset pagination only ~3.5x faster than OFFSET at page 2500 of a 100k-row table
(scripts/benchmark_pagination.py), because both queries degraded to a full scan + sort.
See docs/performance.md for the before/after numbers with this index in place.
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ASC, not DESC: Postgres can scan a btree backward just as efficiently, so a plain
    # ascending index serves both the DESC-ordered listing query and any future
    # ascending one -- and it matches the plain Index(...) declared on the ORM model.
    op.execute("CREATE INDEX idx_tickets_created_at_id ON tickets (created_at, id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_tickets_created_at_id")
