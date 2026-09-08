import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.ticket import AISuggestion
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository


async def _make_customer(session):
    return await UserRepository(session).create(
        email=f"{uuid.uuid4()}@example.com", hashed_password="x", role="customer"
    )


@pytest.mark.asyncio
async def test_idempotency_key_unique_constraint_is_enforced_by_the_db(db_session):
    customer = await _make_customer(db_session)
    repo = TicketRepository(db_session)

    await repo.create(customer.id, "Subject", "Body", "dup-key", None)

    with pytest.raises(IntegrityError):
        await repo.create(customer.id, "Other subject", "Other body", "dup-key", None)


@pytest.mark.asyncio
async def test_keyset_pagination_covers_all_rows_without_duplicates(db_session):
    customer = await _make_customer(db_session)
    repo = TicketRepository(db_session)
    created = [
        await repo.create(customer.id, f"Subject {i}", "Body", None, None) for i in range(5)
    ]

    seen_ids: list[uuid.UUID] = []
    cursor = None
    for _ in range(10):  # generous upper bound on page count to avoid an infinite loop on a bug
        page = await repo.list_paginated(customer_id=customer.id, cursor=cursor, limit=2)
        if not page:
            break
        seen_ids.extend(t.id for t in page)
        last = page[-1]
        cursor = (last.created_at, last.id)

    assert len(seen_ids) == len(created)
    assert len(set(seen_ids)) == len(created)  # no row repeated across pages


@pytest.mark.asyncio
async def test_deleting_ticket_cascades_to_its_ai_suggestion(db_session):
    customer = await _make_customer(db_session)
    repo = TicketRepository(db_session)
    ticket = await repo.create(customer.id, "Subject", "Body", None, None)

    db_session.add(
        AISuggestion(ticket_id=ticket.id, suggested_reply="draft", source_article_ids=[])
    )
    await db_session.flush()

    await db_session.delete(ticket)
    await db_session.flush()

    result = await db_session.execute(
        select(AISuggestion).where(AISuggestion.ticket_id == ticket.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_get_by_id_returns_none_for_missing_ticket(db_session):
    repo = TicketRepository(db_session)

    assert await repo.get_by_id(uuid.uuid4()) is None
