import uuid

import pytest

from app.core.enums import TicketStatus, UserRole
from app.core.exceptions import (
    IdempotencyConflictError,
    InvalidStateTransitionError,
    NotFoundError,
    UnauthorizedActionError,
)
from app.models.user import User
from app.services.ticket_service import TicketService
from tests.fakes import FakeTicketCommentRepository, FakeTicketRepository, FakeUserRepository


def make_user(role: UserRole) -> User:
    return User(
        id=uuid.uuid4(), email=f"{role.value}@example.com", hashed_password="x", role=role.value
    )


@pytest.fixture
def user_repo() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def ticket_service(user_repo: FakeUserRepository) -> TicketService:
    return TicketService(FakeTicketRepository(), user_repo, FakeTicketCommentRepository())


@pytest.mark.asyncio
async def test_create_ticket_sets_pending_status_and_sla_deadline(ticket_service: TicketService):
    customer = make_user(UserRole.CUSTOMER)

    ticket = await ticket_service.create_ticket(customer.id, "Can't log in", "Help", "key-1")

    assert ticket.status == TicketStatus.PENDING
    assert ticket.sla_deadline is not None


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_same_payload_returns_same_ticket(
    ticket_service: TicketService,
):
    customer = make_user(UserRole.CUSTOMER)

    first = await ticket_service.create_ticket(customer.id, "Subject", "Body", "dup-key")
    second = await ticket_service.create_ticket(customer.id, "Subject", "Body", "dup-key")

    assert first.id == second.id


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_different_payload_conflicts(
    ticket_service: TicketService,
):
    customer = make_user(UserRole.CUSTOMER)
    await ticket_service.create_ticket(customer.id, "Subject", "Body", "dup-key")

    with pytest.raises(IdempotencyConflictError):
        await ticket_service.create_ticket(customer.id, "Different", "Body", "dup-key")


@pytest.mark.asyncio
async def test_customer_cannot_view_another_customers_ticket(ticket_service: TicketService):
    owner = make_user(UserRole.CUSTOMER)
    stranger = make_user(UserRole.CUSTOMER)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)

    with pytest.raises(UnauthorizedActionError):
        await ticket_service.get_ticket_for_user(ticket.id, stranger)


@pytest.mark.asyncio
async def test_owner_customer_can_view_own_ticket(ticket_service: TicketService):
    owner = make_user(UserRole.CUSTOMER)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)

    fetched = await ticket_service.get_ticket_for_user(ticket.id, owner)

    assert fetched.id == ticket.id


@pytest.mark.asyncio
async def test_admin_can_view_any_ticket(ticket_service: TicketService):
    owner = make_user(UserRole.CUSTOMER)
    admin = make_user(UserRole.ADMIN)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)

    fetched = await ticket_service.get_ticket_for_user(ticket.id, admin)

    assert fetched.id == ticket.id


@pytest.mark.asyncio
async def test_get_ticket_not_found_raises(ticket_service: TicketService):
    admin = make_user(UserRole.ADMIN)

    with pytest.raises(NotFoundError):
        await ticket_service.get_ticket_for_user(uuid.uuid4(), admin)


@pytest.mark.asyncio
async def test_list_tickets_scopes_customer_to_own_tickets(ticket_service: TicketService):
    owner = make_user(UserRole.CUSTOMER)
    other = make_user(UserRole.CUSTOMER)
    await ticket_service.create_ticket(owner.id, "Mine", "Body", None)
    await ticket_service.create_ticket(other.id, "Not mine", "Body", None)

    tickets, _ = await ticket_service.list_tickets(owner, None, None, None, 20)

    assert len(tickets) == 1
    assert tickets[0].subject == "Mine"


@pytest.mark.asyncio
async def test_list_tickets_admin_sees_all(ticket_service: TicketService):
    owner = make_user(UserRole.CUSTOMER)
    other = make_user(UserRole.CUSTOMER)
    admin = make_user(UserRole.ADMIN)
    await ticket_service.create_ticket(owner.id, "One", "Body", None)
    await ticket_service.create_ticket(other.id, "Two", "Body", None)

    tickets, _ = await ticket_service.list_tickets(admin, None, None, None, 20)

    assert len(tickets) == 2


@pytest.mark.asyncio
async def test_assign_ticket_requires_existing_agent(
    ticket_service: TicketService, user_repo: FakeUserRepository
):
    owner = make_user(UserRole.CUSTOMER)
    admin = make_user(UserRole.ADMIN)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)

    with pytest.raises(NotFoundError):
        await ticket_service.assign_ticket(ticket.id, uuid.uuid4(), admin)


@pytest.mark.asyncio
async def test_assign_ticket_succeeds_for_valid_agent(
    ticket_service: TicketService, user_repo: FakeUserRepository
):
    owner = make_user(UserRole.CUSTOMER)
    admin = make_user(UserRole.ADMIN)
    agent = make_user(UserRole.AGENT)
    user_repo.seed(agent)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)

    updated = await ticket_service.assign_ticket(ticket.id, agent.id, admin)

    assert updated.assigned_agent_id == agent.id


@pytest.mark.asyncio
async def test_cannot_assign_resolved_ticket(
    ticket_service: TicketService, user_repo: FakeUserRepository
):
    owner = make_user(UserRole.CUSTOMER)
    admin = make_user(UserRole.ADMIN)
    agent = make_user(UserRole.AGENT)
    user_repo.seed(agent)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)
    ticket.status = TicketStatus.RESOLVED

    with pytest.raises(InvalidStateTransitionError):
        await ticket_service.assign_ticket(ticket.id, agent.id, admin)


@pytest.mark.asyncio
async def test_update_status_to_in_progress_from_classified(ticket_service: TicketService):
    owner = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)
    ticket.status = TicketStatus.CLASSIFIED

    updated = await ticket_service.update_status(ticket.id, TicketStatus.IN_PROGRESS, agent)

    assert updated.status == TicketStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_cannot_reopen_a_resolved_ticket(ticket_service: TicketService):
    owner = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)
    ticket.status = TicketStatus.RESOLVED

    with pytest.raises(InvalidStateTransitionError):
        await ticket_service.update_status(ticket.id, TicketStatus.IN_PROGRESS, agent)


@pytest.mark.asyncio
async def test_cannot_manually_set_status_to_pending(ticket_service: TicketService):
    owner = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)

    with pytest.raises(InvalidStateTransitionError):
        await ticket_service.update_status(ticket.id, TicketStatus.PENDING, agent)


@pytest.mark.asyncio
async def test_customer_can_comment_on_own_ticket(ticket_service: TicketService):
    owner = make_user(UserRole.CUSTOMER)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)

    comment = await ticket_service.add_comment(ticket.id, owner, "Any update?", False)

    assert comment.body == "Any update?"
    assert comment.is_internal is False


@pytest.mark.asyncio
async def test_customer_cannot_post_internal_note(ticket_service: TicketService):
    owner = make_user(UserRole.CUSTOMER)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)

    with pytest.raises(UnauthorizedActionError):
        await ticket_service.add_comment(ticket.id, owner, "Sneaky internal note", True)


@pytest.mark.asyncio
async def test_customer_cannot_comment_on_others_ticket(ticket_service: TicketService):
    owner = make_user(UserRole.CUSTOMER)
    stranger = make_user(UserRole.CUSTOMER)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)

    with pytest.raises(UnauthorizedActionError):
        await ticket_service.add_comment(ticket.id, stranger, "Not my ticket", False)


@pytest.mark.asyncio
async def test_agent_can_post_internal_note(ticket_service: TicketService):
    owner = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)

    comment = await ticket_service.add_comment(ticket.id, agent, "Internal context", True)

    assert comment.is_internal is True


@pytest.mark.asyncio
async def test_customer_does_not_see_internal_notes(ticket_service: TicketService):
    owner = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)
    await ticket_service.add_comment(ticket.id, agent, "Internal note", True)
    await ticket_service.add_comment(ticket.id, agent, "Customer-facing reply", False)

    comments = await ticket_service.list_comments(ticket.id, owner)

    assert len(comments) == 1
    assert comments[0].body == "Customer-facing reply"


@pytest.mark.asyncio
async def test_agent_sees_all_comments_including_internal(ticket_service: TicketService):
    owner = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    ticket = await ticket_service.create_ticket(owner.id, "Subject", "Body", None)
    await ticket_service.add_comment(ticket.id, agent, "Internal note", True)
    await ticket_service.add_comment(ticket.id, agent, "Customer-facing reply", False)

    comments = await ticket_service.list_comments(ticket.id, agent)

    assert len(comments) == 2
