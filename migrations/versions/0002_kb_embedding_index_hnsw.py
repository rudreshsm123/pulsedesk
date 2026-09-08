"""switch kb_chunks embedding index from ivfflat to hnsw

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-09

ivfflat partitions vectors into "lists" via k-means at index-creation time. Since our
migration creates this index before any KB articles exist, the index trains on zero
rows and Postgres itself warns "ivfflat index created with little data ... This will
cause low recall" -- in practice this manifested as similarity search silently
returning zero rows for a KB article that had just been indexed, so every ticket fell
back to the "not enough information" reply regardless of how well the ticket matched
the knowledge base. HNSW builds its graph incrementally as rows are inserted, so it
gives correct results from the very first row instead of requiring a large bulk load
(or a manual REINDEX) before it becomes usable.
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_kb_chunks_embedding")
    op.execute(
        "CREATE INDEX idx_kb_chunks_embedding ON kb_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_kb_chunks_embedding")
    op.execute(
        "CREATE INDEX idx_kb_chunks_embedding ON kb_chunks "
        "USING ivfflat (embedding vector_cosine_ops)"
    )
