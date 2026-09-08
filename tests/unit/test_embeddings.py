import math

from app.models.kb import EMBEDDING_DIM
from app.services.embeddings import HashingEmbeddingProvider


def cosine_similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_embedding_has_expected_dimension_and_is_normalized():
    provider = HashingEmbeddingProvider()
    vector = provider.embed("How do I reset my password?")

    assert len(vector) == EMBEDDING_DIM
    norm = math.sqrt(sum(v * v for v in vector))
    assert math.isclose(norm, 1.0, abs_tol=1e-6)


def test_embedding_is_deterministic():
    provider = HashingEmbeddingProvider()
    text = "Refund request for last invoice"

    assert provider.embed(text) == provider.embed(text)


def test_similar_text_is_more_similar_than_unrelated_text():
    provider = HashingEmbeddingProvider()
    query = provider.embed("How do I reset my account password?")
    related = provider.embed("Steps to reset your password and regain account access")
    unrelated = provider.embed("Our quarterly revenue grew due to new pricing tiers")

    assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)


def test_empty_text_returns_zero_vector():
    provider = HashingEmbeddingProvider()
    vector = provider.embed("")

    assert vector == [0.0] * EMBEDDING_DIM
