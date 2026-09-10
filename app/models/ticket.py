import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import TicketPriority, TicketStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Ticket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','CLASSIFIED','IN_PROGRESS','RESOLVED','BREACHED')",
            name="ck_tickets_status",
        ),
        CheckConstraint(
            "priority IS NULL OR priority IN ('LOW','MEDIUM','HIGH','URGENT')",
            name="ck_tickets_priority",
        ),
        # Matches the exact WHERE/ORDER BY shape of the periodic SLA-sweep query
        # (see app/workers/sla_sweep.py) so it hits an index scan, not a seq scan,
        # as the tickets table grows -- documented with before/after numbers in
        # docs/performance.md.
        Index("idx_tickets_sla_sweep", "status", "priority", "sla_deadline"),
        Index("idx_tickets_customer", "customer_id"),
        Index("idx_tickets_agent", "assigned_agent_id"),
        # Supports keyset pagination's WHERE (created_at, id) < :cursor ORDER BY
        # created_at DESC, id DESC (TicketRepository.list_paginated) as an index seek
        # instead of a full scan+sort -- see docs/performance.md.
        Index("idx_tickets_created_at_id", "created_at", "id"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        String(20), nullable=False, default=TicketStatus.PENDING
    )
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    priority: Mapped[TicketPriority | None] = mapped_column(String(10), nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True
    )
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    ai_suggestion: Mapped["AISuggestion | None"] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", uselist=False
    )


class AISuggestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_suggestions"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    suggested_reply: Mapped[str] = mapped_column(Text, nullable=False)
    source_article_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="ai_suggestion")


class TicketComment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ticket_comments"
    __table_args__ = (Index("idx_ticket_comments_ticket", "ticket_id", "created_at"),)

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Internal notes are agent/admin-only shop talk ("customer is on a legacy plan,
    # check billing table X") -- never returned to a customer's own comment feed.
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
