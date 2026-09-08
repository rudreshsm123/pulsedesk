import pytest

from app.repositories.kb_repository import KBArticleRepository, KBChunkRepository
from app.services.embeddings import HashingEmbeddingProvider
from app.services.kb_service import KBService


@pytest.mark.asyncio
async def test_search_similar_ranks_the_relevant_article_first(db_session):
    # Regression test for the migration-0002 bug: an ivfflat index trained on an empty
    # table silently returned zero results even for an obviously-matching chunk. This
    # exercises the real HNSW index end-to-end (chunk -> embed -> insert -> search)
    # against a live Postgres, not a fake, so a future regression here would be caught.
    embeddings = HashingEmbeddingProvider()
    articles = KBArticleRepository(db_session)
    chunks = KBChunkRepository(db_session)
    service = KBService(articles, chunks, embeddings)

    password_article = await service.create_article(
        "Password Reset",
        "To reset your password, go to Settings, then Security, then Reset Password.",
    )
    billing_article = await service.create_article(
        "Billing", "Invoices are issued monthly and can be downloaded from the billing tab."
    )
    await db_session.flush()

    await service.reindex_article(password_article.id)
    await service.reindex_article(billing_article.id)
    await db_session.flush()

    query_embedding = embeddings.embed("I forgot my password and cannot log in")
    results = await chunks.search_similar(query_embedding, top_k=2)

    assert len(results) == 2
    top_chunk, top_similarity = results[0]
    assert top_chunk.article_id == password_article.id
    assert top_similarity > results[1][1]


@pytest.mark.asyncio
async def test_search_similar_returns_empty_list_when_no_chunks_exist(db_session):
    embeddings = HashingEmbeddingProvider()
    chunks = KBChunkRepository(db_session)

    results = await chunks.search_similar(embeddings.embed("anything"), top_k=3)

    assert results == []
