import uuid

import pytest
from sqlalchemy import select

from app.models.ticket import TicketComment
from app.repositories.ticket_comment_repository import TicketCommentRepository
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository


async def _make_customer(session):
    return await UserRepository(session).create(
        email=f"{uuid.uuid4()}@example.com", hashed_password="x", role="customer"
    )


@pytest.mark.asyncio
async def test_comments_are_returned_in_chronological_order(db_session):
    customer = await _make_customer(db_session)
    ticket = await TicketRepository(db_session).create(
        customer.id, "Subject", "Body", None, None
    )
    comments_repo = TicketCommentRepository(db_session)

    await comments_repo.create(ticket.id, customer.id, "First", False)
    await comments_repo.create(ticket.id, customer.id, "Second", False)
    await comments_repo.create(ticket.id, customer.id, "Third", False)

    comments = await comments_repo.list_by_ticket(ticket.id)

    assert [c.body for c in comments] == ["First", "Second", "Third"]


@pytest.mark.asyncio
async def test_deleting_ticket_cascades_to_its_comments(db_session):
    customer = await _make_customer(db_session)
    ticket = await TicketRepository(db_session).create(
        customer.id, "Subject", "Body", None, None
    )
    comments_repo = TicketCommentRepository(db_session)
    await comments_repo.create(ticket.id, customer.id, "A comment", False)
    await db_session.flush()

    await db_session.delete(ticket)
    await db_session.flush()

    result = await db_session.execute(
        select(TicketComment).where(TicketComment.ticket_id == ticket.id)
    )
    assert result.scalar_one_or_none() is None
