import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TicketPriority, TicketStatus
from app.models.ticket import Ticket


class TicketRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, ticket_id: uuid.UUID) -> Ticket | None:
        result = await self._session.execute(select(Ticket).where(Ticket.id == ticket_id))
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Ticket | None:
        result = await self._session.execute(
            select(Ticket).where(Ticket.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        customer_id: uuid.UUID,
        subject: str,
        body: str,
        idempotency_key: str | None,
        sla_deadline: datetime | None,
    ) -> Ticket:
        ticket = Ticket(
            customer_id=customer_id,
            subject=subject,
            body=body,
            idempotency_key=idempotency_key,
            sla_deadline=sla_deadline,
            status=TicketStatus.PENDING,
        )
        self._session.add(ticket)
        await self._session.flush()
        await self._session.refresh(ticket)
        return ticket

    async def list_paginated(
        self,
        *,
        customer_id: uuid.UUID | None = None,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        cursor: tuple[datetime, uuid.UUID] | None = None,
        limit: int = 20,
    ) -> list[Ticket]:
        # Keyset pagination (WHERE (created_at, id) < cursor ORDER BY ... LIMIT) instead of
        # OFFSET/LIMIT: OFFSET forces Postgres to scan and discard every prior row, which
        # degrades linearly as agents page deeper into a large ticket table (measured in
        # docs/performance.md). Keyset pagination stays a constant-time index seek.
        stmt = select(Ticket)

        if customer_id is not None:
            stmt = stmt.where(Ticket.customer_id == customer_id)
        if status is not None:
            stmt = stmt.where(Ticket.status == status)
        if priority is not None:
            stmt = stmt.where(Ticket.priority == priority)

        if cursor is not None:
            cursor_created_at, cursor_id = cursor
            stmt = stmt.where(
                or_(
                    Ticket.created_at < cursor_created_at,
                    and_(Ticket.created_at == cursor_created_at, Ticket.id < cursor_id),
                )
            )

        stmt = stmt.order_by(Ticket.created_at.desc(), Ticket.id.desc()).limit(limit)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def assign_agent(self, ticket: Ticket, agent_id: uuid.UUID) -> Ticket:
        ticket.assigned_agent_id = agent_id
        await self._session.flush()
        await self._session.refresh(ticket)
        return ticket
