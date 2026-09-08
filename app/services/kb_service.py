import uuid

from app.models.kb import KBArticle
from app.repositories.kb_repository import KBArticleRepository, KBChunkRepository
from app.services.chunking import chunk_text
from app.services.embeddings import EmbeddingProvider


class KBService:
    def __init__(
        self,
        article_repository: KBArticleRepository,
        chunk_repository: KBChunkRepository,
        embedding_provider: EmbeddingProvider,
    ):
        self._articles = article_repository
        self._chunks = chunk_repository
        self._embeddings = embedding_provider

    async def create_article(self, title: str, body: str) -> KBArticle:
        return await self._articles.create(title, body)

    async def reindex_article(self, article_id: uuid.UUID) -> None:
        article = await self._articles.get_by_id(article_id)
        if article is None:
            return

        pieces = chunk_text(article.body)
        chunks = [(piece, self._embeddings.embed(piece)) for piece in pieces]
        await self._chunks.replace_chunks(article_id, chunks)
