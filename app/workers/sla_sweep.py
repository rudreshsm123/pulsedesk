from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import AsyncSessionFactory
from app.core.enums import TicketStatus
from app.core.logging import get_logger
from app.models.ticket import Ticket
from app.workers.celery_app import celery_app
from app.workers.task_runner import run_task

logger = get_logger("pulsedesk.workers.sla_sweep")

_OPEN_STATUSES = (TicketStatus.PENDING, TicketStatus.CLASSIFIED, TicketStatus.IN_PROGRESS)


@celery_app.task(name="app.workers.sla_sweep.sweep_sla_breaches")
def sweep_sla_breaches() -> int:
    return run_task(_sweep_sla_breaches())


async def _sweep_sla_breaches() -> int:
    now = datetime.now(UTC)

    async with AsyncSessionFactory() as session:
        # FOR UPDATE SKIP LOCKED: if a second beat/worker instance runs this concurrently
        # (e.g. during a deploy overlap), each row is claimed by exactly one sweeper instead
        # of both racing to flag -- and skip_locked keeps the second sweeper from blocking on
        # rows the first one already has locked, so it just picks up the remaining ones.
        stmt = (
            select(Ticket)
            .where(Ticket.status.in_(_OPEN_STATUSES))
            .where(Ticket.sla_deadline.is_not(None))
            .where(Ticket.sla_deadline < now)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        breached_tickets = list(result.scalars().all())

        for ticket in breached_tickets:
            ticket.status = TicketStatus.BREACHED

        await session.commit()

    if breached_tickets:
        logger.info(f"sla_sweep: flagged {len(breached_tickets)} ticket(s) as BREACHED")

    return len(breached_tickets)
