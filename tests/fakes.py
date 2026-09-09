import uuid
from datetime import UTC, datetime

from app.core.enums import TicketStatus
from app.models.ticket import Ticket
from app.models.user import User


class FakeUserRepository:
    """In-memory stand-in for UserRepository so service logic is tested without a real DB."""

    def __init__(self):
        self._users_by_email: dict[str, User] = {}
        self._users_by_id: dict[uuid.UUID, User] = {}

    async def get_by_email(self, email: str) -> User | None:
        return self._users_by_email.get(email)

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._users_by_id.get(user_id)

    async def create(self, email: str, hashed_password: str, role: str) -> User:
        user = User(id=uuid.uuid4(), email=email, hashed_password=hashed_password, role=role)
        self._users_by_email[email] = user
        self._users_by_id[user.id] = user
        return user

    def seed(self, user: User) -> None:
        self._users_by_email[user.email] = user
        self._users_by_id[user.id] = user


class FakeTicketRepository:
    """In-memory stand-in for TicketRepository so ticket service logic (idempotency,
    RBAC-scoped listing, assignment state transitions) is tested without a real DB."""

    def __init__(self):
        self._tickets: dict[uuid.UUID, Ticket] = {}

    async def get_by_id(self, ticket_id: uuid.UUID) -> Ticket | None:
        return self._tickets.get(ticket_id)

    async def get_by_idempotency_key(self, key: str) -> Ticket | None:
        return next((t for t in self._tickets.values() if t.idempotency_key == key), None)

    async def create(
        self, customer_id, subject, body, idempotency_key, sla_deadline
    ) -> Ticket:
        ticket = Ticket(
            id=uuid.uuid4(),
            customer_id=customer_id,
            subject=subject,
            body=body,
            idempotency_key=idempotency_key,
            sla_deadline=sla_deadline,
            status=TicketStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._tickets[ticket.id] = ticket
        return ticket

    async def list_paginated(
        self, *, customer_id=None, status=None, priority=None, cursor=None, limit=20
    ) -> list[Ticket]:
        items = list(self._tickets.values())
        if customer_id is not None:
            items = [t for t in items if t.customer_id == customer_id]
        if status is not None:
            items = [t for t in items if t.status == status]
        if priority is not None:
            items = [t for t in items if t.priority == priority]

        items.sort(key=lambda t: (t.created_at, t.id), reverse=True)

        if cursor is not None:
            cursor_created_at, cursor_id = cursor
            items = [
                t
                for t in items
                if (t.created_at, t.id) < (cursor_created_at, cursor_id)
            ]

        return items[:limit]

    async def assign_agent(self, ticket: Ticket, agent_id: uuid.UUID) -> Ticket:
        ticket.assigned_agent_id = agent_id
        return ticket

    def seed(self, ticket: Ticket) -> None:
        self._tickets[ticket.id] = ticket
