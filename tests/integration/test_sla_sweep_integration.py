import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.enums import TicketStatus
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository
from app.workers import sla_sweep
from app.workers.sla_sweep import _sweep_sla_breaches


@pytest.mark.asyncio
async def test_sweep_flags_overdue_open_tickets_and_leaves_others_alone(
    db_session, database_url, monkeypatch
):
    # _sweep_sla_breaches opens its own session via the module-level AsyncSessionFactory
    # imported from app.core.db, which points at the dev DB (DATABASE_URL from .env),
    # not this test's ephemeral Testcontainers instance. Point it at the same container
    # db_session is using so the worker and the test observe the same data.
    test_engine = create_async_engine(database_url)
    monkeypatch.setattr(
        sla_sweep, "AsyncSessionFactory", async_sessionmaker(test_engine, expire_on_commit=False)
    )

    customer = await UserRepository(db_session).create(
        email=f"{uuid.uuid4()}@example.com", hashed_password="x", role="customer"
    )
    repo = TicketRepository(db_session)
    now = datetime.now(timezone.utc)

    overdue = await repo.create(customer.id, "Overdue", "Body", None, now - timedelta(hours=1))
    not_due_yet = await repo.create(customer.id, "Not due", "Body", None, now + timedelta(hours=1))
    already_resolved = await repo.create(
        customer.id, "Resolved", "Body", None, now - timedelta(hours=1)
    )
    already_resolved.status = TicketStatus.RESOLVED
    await db_session.flush()

    # _sweep_sla_breaches runs in its own session/transaction, so commit here first so
    # it can see these rows.
    await db_session.commit()

    breached_count = await _sweep_sla_breaches()
    await test_engine.dispose()

    await db_session.refresh(overdue)
    await db_session.refresh(not_due_yet)
    await db_session.refresh(already_resolved)

    assert breached_count >= 1
    assert overdue.status == TicketStatus.BREACHED
    assert not_due_yet.status == TicketStatus.PENDING
    assert already_resolved.status == TicketStatus.RESOLVED
