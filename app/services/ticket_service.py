import uuid
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.enums import TicketPriority, TicketStatus, UserRole
from app.core.exceptions import (
    IdempotencyConflictError,
    InvalidStateTransitionError,
    NotFoundError,
    UnauthorizedActionError,
)
from app.core.pagination import decode_cursor, encode_cursor
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository

settings = get_settings()


class TicketService:
    def __init__(self, ticket_repository: TicketRepository, user_repository: UserRepository):
        self._tickets = ticket_repository
        self._users = user_repository

    async def create_ticket(
        self,
        customer_id: uuid.UUID,
        subject: str,
        body: str,
        idempotency_key: str | None,
    ) -> Ticket:
        if idempotency_key is not None:
            existing = await self._tickets.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                if existing.subject == subject and existing.body == body:
                    return existing
                raise IdempotencyConflictError()

        sla_deadline = datetime.now(UTC) + timedelta(hours=settings.default_sla_hours)
        return await self._tickets.create(
            customer_id=customer_id,
            subject=subject,
            body=body,
            idempotency_key=idempotency_key,
            sla_deadline=sla_deadline,
        )

    async def get_ticket_for_user(self, ticket_id: uuid.UUID, user: User) -> Ticket:
        ticket = await self._tickets.get_by_id(ticket_id)
        if ticket is None:
            raise NotFoundError("Ticket", str(ticket_id))

        self._authorize_view(ticket, user)
        return ticket

    async def list_tickets(
        self,
        user: User,
        status: TicketStatus | None,
        priority: TicketPriority | None,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[Ticket], str | None]:
        decoded_cursor = decode_cursor(cursor) if cursor else None

        # Customers only ever see their own tickets, enforced server-side -- a customer
        # cannot widen this by passing a different filter, since the field isn't customer
        # -settable at all here.
        customer_filter = user.id if UserRole(user.role) == UserRole.CUSTOMER else None

        tickets = await self._tickets.list_paginated(
            customer_id=customer_filter,
            status=status,
            priority=priority,
            cursor=decoded_cursor,
            limit=limit,
        )

        next_cursor = None
        if len(tickets) == limit and tickets:
            last = tickets[-1]
            next_cursor = encode_cursor(last.created_at, last.id)

        return tickets, next_cursor

    async def assign_ticket(
        self, ticket_id: uuid.UUID, agent_id: uuid.UUID, acting_user: User
    ) -> Ticket:
        ticket = await self._tickets.get_by_id(ticket_id)
        if ticket is None:
            raise NotFoundError("Ticket", str(ticket_id))

        if ticket.status in (TicketStatus.RESOLVED, TicketStatus.BREACHED):
            raise InvalidStateTransitionError(
                f"Cannot assign a ticket in status {ticket.status}"
            )

        agent = await self._users.get_by_id(agent_id)
        if agent is None or UserRole(agent.role) != UserRole.AGENT:
            raise NotFoundError("Agent", str(agent_id))

        return await self._tickets.assign_agent(ticket, agent_id)

    @staticmethod
    def _authorize_view(ticket: Ticket, user: User) -> None:
        role = UserRole(user.role)
        if role == UserRole.ADMIN:
            return
        if role == UserRole.CUSTOMER:
            if ticket.customer_id == user.id:
                return
            raise UnauthorizedActionError("You may only view your own tickets")
        if role == UserRole.AGENT:
            if ticket.assigned_agent_id is None or ticket.assigned_agent_id == user.id:
                return
            raise UnauthorizedActionError("This ticket is assigned to another agent")
