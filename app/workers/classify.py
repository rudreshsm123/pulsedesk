import asyncio
import uuid

from app.core.db import AsyncSessionFactory
from app.core.enums import TicketStatus
from app.core.logging import get_logger
from app.repositories.ticket_repository import TicketRepository
from app.services.classification import classify_ticket_text
from app.workers.celery_app import celery_app

logger = get_logger("pulsedesk.workers.classify")


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=5,
    acks_late=True,
)
def classify_ticket(self, ticket_id: str) -> None:
    asyncio.run(_classify_ticket(uuid.UUID(ticket_id)))


async def _classify_ticket(ticket_id: uuid.UUID) -> None:
    async with AsyncSessionFactory() as session:
        repo = TicketRepository(session)
        ticket = await repo.get_by_id(ticket_id)

        if ticket is None:
            logger.warning(f"classify_ticket: ticket {ticket_id} not found, skipping")
            return

        if ticket.status != TicketStatus.PENDING:
            # Safe no-op: a retried/duplicate task delivery must not reclassify a ticket
            # an earlier attempt already finished (Celery's at-least-once delivery means
            # this task can run more than once for the same ticket).
            logger.info(f"classify_ticket: ticket {ticket_id} already {ticket.status}, skipping")
            return

        category, priority, confidence = classify_ticket_text(ticket.subject, ticket.body)
        ticket.category = category
        ticket.priority = priority
        ticket.ai_confidence = confidence
        ticket.status = TicketStatus.CLASSIFIED

        await session.commit()
