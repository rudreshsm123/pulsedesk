import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.db import get_db
from app.core.enums import UserRole
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.repositories.kb_repository import KBArticleRepository, KBChunkRepository
from app.schemas.kb import KBArticleCreate, KBArticleOut
from app.services.embeddings import get_embedding_provider
from app.services.kb_service import KBService
from app.workers.kb_index import index_kb_article

router = APIRouter(prefix="/kb-articles", tags=["kb-articles"])
logger = get_logger("pulsedesk.api.kb_articles")

require_admin = require_role(UserRole.ADMIN)


def get_kb_service(session: AsyncSession = Depends(get_db)) -> KBService:
    return KBService(
        KBArticleRepository(session), KBChunkRepository(session), get_embedding_provider()
    )


@router.post("", response_model=KBArticleOut, status_code=status.HTTP_201_CREATED)
async def create_kb_article(
    body: KBArticleCreate,
    _admin=Depends(require_admin),
    kb_service: KBService = Depends(get_kb_service),
) -> KBArticleOut:
    article = await kb_service.create_article(body.title, body.body)

    try:
        index_kb_article.delay(str(article.id))
    except Exception:
        # The article is saved either way; if enqueueing fails it just means it won't be
        # searchable via RAG until manually reindexed -- not that article creation failed.
        logger.exception(f"Failed to enqueue indexing for KB article {article.id}")

    return KBArticleOut.model_validate(article)


@router.get("", response_model=list[KBArticleOut])
async def list_kb_articles(
    _admin=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> list[KBArticleOut]:
    articles = await KBArticleRepository(session).list_all()
    return [KBArticleOut.model_validate(a) for a in articles]


@router.get("/{article_id}", response_model=KBArticleOut)
async def get_kb_article(
    article_id: uuid.UUID,
    _admin=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> KBArticleOut:
    article = await KBArticleRepository(session).get_by_id(article_id)
    if article is None:
        raise NotFoundError("KBArticle", str(article_id))
    return KBArticleOut.model_validate(article)
