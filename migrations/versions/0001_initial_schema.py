"""initial schema: users, kb_articles, kb_chunks, tickets, ai_suggestions

Revision ID: 0001
Revises:
Create Date: 2026-09-08
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("role IN ('customer','agent','admin')", name="ck_users_role"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "kb_articles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "kb_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "article_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kb_articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
    )
    op.execute(
        "CREATE INDEX idx_kb_chunks_embedding ON kb_chunks "
        "USING ivfflat (embedding vector_cosine_ops)"
    )

    op.create_table(
        "tickets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "assigned_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("priority", sa.String(10), nullable=True),
        sa.Column("ai_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=True, unique=True),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','CLASSIFIED','IN_PROGRESS','RESOLVED','BREACHED')",
            name="ck_tickets_status",
        ),
        sa.CheckConstraint(
            "priority IS NULL OR priority IN ('LOW','MEDIUM','HIGH','URGENT')",
            name="ck_tickets_priority",
        ),
    )
    op.create_index("idx_tickets_sla_sweep", "tickets", ["status", "priority", "sla_deadline"])
    op.create_index("idx_tickets_customer", "tickets", ["customer_id"])
    op.create_index("idx_tickets_agent", "tickets", ["assigned_agent_id"])

    op.create_table(
        "ai_suggestions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "ticket_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("suggested_reply", sa.Text, nullable=False),
        sa.Column(
            "source_article_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_suggestions")
    op.drop_index("idx_tickets_agent", table_name="tickets")
    op.drop_index("idx_tickets_customer", table_name="tickets")
    op.drop_index("idx_tickets_sla_sweep", table_name="tickets")
    op.drop_table("tickets")
    op.execute("DROP INDEX IF EXISTS idx_kb_chunks_embedding")
    op.drop_table("kb_chunks")
    op.drop_table("kb_articles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
