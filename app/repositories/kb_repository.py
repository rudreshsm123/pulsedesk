import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb import KBArticle, KBChunk


class KBArticleRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, title: str, body: str) -> KBArticle:
        article = KBArticle(title=title, body=body)
        self._session.add(article)
        await self._session.flush()
        await self._session.refresh(article)
        return article

    async def get_by_id(self, article_id: uuid.UUID) -> KBArticle | None:
        result = await self._session.execute(
            select(KBArticle).where(KBArticle.id == article_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 50) -> list[KBArticle]:
        result = await self._session.execute(
            select(KBArticle).order_by(KBArticle.updated_at.desc()).limit(limit)
        )
        return list(result.scalars().all())


class KBChunkRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def replace_chunks(
        self, article_id: uuid.UUID, chunks: list[tuple[str, list[float]]]
    ) -> None:
        await self._session.execute(delete(KBChunk).where(KBChunk.article_id == article_id))
        for chunk_text, embedding in chunks:
            self._session.add(
                KBChunk(article_id=article_id, chunk_text=chunk_text, embedding=embedding)
            )
        await self._session.flush()

    async def search_similar(self, query_embedding: list[float], top_k: int = 3) -> list[tuple]:
        """Returns (KBChunk, cosine_similarity) pairs, most similar first. pgvector's
        cosine_distance() is 1 - cosine_similarity, so we convert back for callers that
        want a similarity score to threshold against."""
        distance = KBChunk.embedding.cosine_distance(query_embedding)
        stmt = select(KBChunk, distance).order_by(distance).limit(top_k)
        result = await self._session.execute(stmt)
        return [(chunk, 1 - dist) for chunk, dist in result.all()]
