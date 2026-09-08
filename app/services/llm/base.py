import uuid
from dataclasses import dataclass
from typing import Protocol

from app.core.enums import TicketPriority


@dataclass(frozen=True)
class ClassificationResult:
    category: str
    priority: TicketPriority
    confidence: float


@dataclass(frozen=True)
class RetrievedChunk:
    article_id: uuid.UUID
    chunk_text: str
    similarity: float


@dataclass(frozen=True)
class ResolutionDraft:
    reply_text: str
    source_article_ids: list[uuid.UUID]


class LLMProvider(Protocol):
    def classify(self, subject: str, body: str) -> ClassificationResult: ...

    def generate_resolution(
        self, ticket_text: str, retrieved_chunks: list[RetrievedChunk]
    ) -> ResolutionDraft: ...
