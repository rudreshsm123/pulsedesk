import asyncio
import uuid

from app.core.db import AsyncSessionFactory
from app.core.logging import get_logger
from app.repositories.kb_repository import KBArticleRepository, KBChunkRepository
from app.services.embeddings import get_embedding_provider
from app.services.kb_service import KBService
from app.workers.celery_app import celery_app

logger = get_logger("pulsedesk.workers.kb_index")


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=5,
    acks_late=True,
)
def index_kb_article(self, article_id: str) -> None:
    asyncio.run(_index_kb_article(uuid.UUID(article_id)))


async def _index_kb_article(article_id: uuid.UUID) -> None:
    async with AsyncSessionFactory() as session:
        service = KBService(
            KBArticleRepository(session), KBChunkRepository(session), get_embedding_provider()
        )
        await service.reindex_article(article_id)
        await session.commit()

    logger.info(f"kb_index: reindexed article {article_id}")
