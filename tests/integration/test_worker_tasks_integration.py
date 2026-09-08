import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.enums import TicketStatus
from app.models.ticket import AISuggestion
from app.repositories.kb_repository import KBArticleRepository
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository
from app.workers import classify, kb_index, rag_suggest
from app.workers.classify import _classify_ticket
from app.workers.kb_index import _index_kb_article
from app.workers.rag_suggest import _generate_suggestion


@pytest.fixture
async def patched_worker_sessions(database_url, monkeypatch):
    # Same reasoning as the SLA sweep integration test: these worker coroutines import
    # their own AsyncSessionFactory from app.core.db (bound to the dev DB), so redirect
    # each worker module's copy at the ephemeral Testcontainers database for the test.
    test_engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    for module in (classify, kb_index, rag_suggest):
        monkeypatch.setattr(module, "AsyncSessionFactory", session_factory)
    yield
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_classify_then_generate_suggestion_grounds_reply_in_kb(
    db_session, patched_worker_sessions
):
    customer = await UserRepository(db_session).create(
        email=f"{uuid.uuid4()}@example.com", hashed_password="x", role="customer"
    )
    kb_article = await KBArticleRepository(db_session).create(
        "Password Reset",
        "To reset your password, go to Settings, then Security, then Reset Password.",
    )
    ticket = await TicketRepository(db_session).create(
        customer.id,
        "Cannot reset password",
        "My password reset email never arrives.",
        None,
        None,
    )
    await db_session.commit()

    await _index_kb_article(kb_article.id)
    await _classify_ticket(ticket.id)
    await _generate_suggestion(ticket.id)

    await db_session.refresh(ticket)
    assert ticket.status == TicketStatus.CLASSIFIED
    assert ticket.priority is not None

    result = await db_session.execute(
        select(AISuggestion).where(AISuggestion.ticket_id == ticket.id)
    )
    suggestion = result.scalar_one()
    assert kb_article.id in suggestion.source_article_ids
    assert "Reset Password" in suggestion.suggested_reply


@pytest.mark.asyncio
async def test_classify_is_a_no_op_on_already_classified_ticket(
    db_session, patched_worker_sessions
):
    customer = await UserRepository(db_session).create(
        email=f"{uuid.uuid4()}@example.com", hashed_password="x", role="customer"
    )
    ticket = await TicketRepository(db_session).create(
        customer.id, "Subject", "Body", None, None
    )
    ticket.status = TicketStatus.CLASSIFIED
    ticket.category = "billing"
    await db_session.commit()

    await _classify_ticket(ticket.id)

    await db_session.refresh(ticket)
    assert ticket.category == "billing"  # untouched by the redundant classify call
