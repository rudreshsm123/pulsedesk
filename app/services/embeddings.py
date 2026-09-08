import hashlib
import math
import re
from typing import Protocol

from app.models.kb import EMBEDDING_DIM

_WORD_RE = re.compile(r"[a-z0-9]+")


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


class HashingEmbeddingProvider:
    """Local, deterministic, zero-cost embedding using the hashing trick (the same idea
    behind scikit-learn's HashingVectorizer): each word hashes to a dimension and votes
    +1/-1, and the result is L2-normalized so cosine similarity behaves sanely. This is
    the "mock"/no-API-key embedding backend -- it captures keyword overlap well enough to
    exercise the whole RAG pipeline (chunking, pgvector search, grounded generation) end
    to end without any external dependency or cost. Swap in a real sentence-embedding
    model/API here once one is available; nothing else in the RAG pipeline needs to change
    since it only depends on this Protocol.
    """

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIM
        words = _WORD_RE.findall(text.lower())

        for word in words:
            digest = hashlib.sha256(word.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]


def get_embedding_provider() -> EmbeddingProvider:
    return HashingEmbeddingProvider()
