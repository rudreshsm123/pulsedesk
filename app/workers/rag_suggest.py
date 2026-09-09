import uuid

from app.core.db import AsyncSessionFactory
from app.core.logging import get_logger
from app.repositories.ai_suggestion_repository import AISuggestionRepository
from app.repositories.kb_repository import KBChunkRepository
from app.repositories.ticket_repository import TicketRepository
from app.services.embeddings import get_embedding_provider
from app.services.llm.base import RetrievedChunk
from app.services.llm.factory import get_llm_provider
from app.services.llm.mock_provider import MockLLMProvider
from app.workers.celery_app import celery_app
from app.workers.task_runner import run_task

logger = get_logger("pulsedesk.workers.rag_suggest")

_TOP_K = 3


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=5,
    acks_late=True,
)
def generate_suggestion(self, ticket_id: str) -> None:
    run_task(_generate_suggestion(uuid.UUID(ticket_id)))


async def _generate_suggestion(ticket_id: uuid.UUID) -> None:
    async with AsyncSessionFactory() as session:
        ticket_repo = TicketRepository(session)
        suggestion_repo = AISuggestionRepository(session)

        ticket = await ticket_repo.get_by_id(ticket_id)
        if ticket is None:
            logger.warning(f"generate_suggestion: ticket {ticket_id} not found, skipping")
            return

        if await suggestion_repo.get_by_ticket_id(ticket_id) is not None:
            # Safe no-op on redelivery: a suggestion already exists for this ticket
            # (ai_suggestions.ticket_id is unique), so this is a retried/duplicate task.
            logger.info(f"generate_suggestion: ticket {ticket_id} already has a suggestion")
            return

        ticket_text = f"{ticket.subject}\n{ticket.body}"
        embedding_provider = get_embedding_provider()
        query_embedding = embedding_provider.embed(ticket_text)

        chunk_repo = KBChunkRepository(session)
        results = await chunk_repo.search_similar(query_embedding, top_k=_TOP_K)
        retrieved = [
            RetrievedChunk(article_id=chunk.article_id, chunk_text=chunk.chunk_text, similarity=sim)
            for chunk, sim in results
        ]

        try:
            draft = get_llm_provider().generate_resolution(ticket_text, retrieved)
        except Exception:
            # Mirrors classify_ticket's fallback: a down/unbilled/rate-limited real
            # provider must not leave the ticket permanently stuck retrying with no
            # suggestion ever produced. MockLLMProvider is always available (no API
            # call) and safe to fall back to -- it's extractive/threshold-gated, so it
            # degrades to an honest "not enough information" rather than a guess.
            logger.exception(
                f"generate_suggestion: LLM call failed for {ticket_id}, using extractive fallback"
            )
            draft = MockLLMProvider().generate_resolution(ticket_text, retrieved)

        await suggestion_repo.create(
            ticket_id=ticket_id,
            suggested_reply=draft.reply_text,
            source_article_ids=draft.source_article_ids,
        )
        await session.commit()

    logger.info(f"generate_suggestion: stored suggestion for ticket {ticket_id}")
