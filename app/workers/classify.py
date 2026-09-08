import uuid

from app.core.db import AsyncSessionFactory
from app.core.enums import TicketStatus
from app.core.logging import get_logger
from app.repositories.ticket_repository import TicketRepository
from app.services.classification import classify_ticket_text
from app.services.llm.mock_provider import get_llm_provider
from app.workers.celery_app import celery_app
from app.workers.task_runner import run_task

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
    run_task(_classify_ticket(uuid.UUID(ticket_id)))


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

        try:
            result = get_llm_provider().classify(ticket.subject, ticket.body)
            category, priority, confidence = result.category, result.priority, result.confidence
        except Exception:
            # Never let an LLM-path failure block classification -- fall back to the
            # always-available rule-based classifier so the ticket still gets triaged.
            logger.exception(
                f"classify_ticket: LLM classification failed for {ticket_id}, using rule fallback"
            )
            category, priority, confidence = classify_ticket_text(ticket.subject, ticket.body)

        ticket.category = category
        ticket.priority = priority
        ticket.ai_confidence = confidence
        ticket.status = TicketStatus.CLASSIFIED

        await session.commit()

    _enqueue_suggestion(str(ticket_id))


def _enqueue_suggestion(ticket_id: str) -> None:
    try:
        from app.workers.rag_suggest import generate_suggestion

        generate_suggestion.delay(ticket_id)
    except Exception:
        logger.exception(f"Failed to enqueue RAG suggestion for ticket {ticket_id}")
