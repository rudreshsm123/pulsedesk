from app.services.classification import classify_ticket_text
from app.services.llm.base import (
    NO_GROUNDING_REPLY,
    SIMILARITY_THRESHOLD,
    ClassificationResult,
    ResolutionDraft,
    RetrievedChunk,
)

_DRAFT_DISCLAIMER = (
    "[Automated draft -- grounded in the knowledge base excerpts below. "
    "Review before sending to the customer.]"
)


class MockLLMProvider:
    """No-API-key backend: classification delegates to the deterministic rule-based
    classifier (app/services/classification.py) and resolution drafting is purely
    extractive over retrieved KB chunks -- it never generates text beyond what's in the
    KB, so it cannot hallucinate. Swap in a real provider (OpenAI/Anthropic) behind this
    same LLMProvider interface once an API key is configured; nothing calling
    get_llm_provider() needs to change.
    """

    def classify(self, subject: str, body: str) -> ClassificationResult:
        category, priority, confidence = classify_ticket_text(subject, body)
        return ClassificationResult(category=category, priority=priority, confidence=confidence)

    def generate_resolution(
        self, ticket_text: str, retrieved_chunks: list[RetrievedChunk]
    ) -> ResolutionDraft:
        grounded_chunks = [c for c in retrieved_chunks if c.similarity >= SIMILARITY_THRESHOLD]

        if not grounded_chunks:
            return ResolutionDraft(reply_text=NO_GROUNDING_REPLY, source_article_ids=[])

        best = grounded_chunks[0]
        reply_text = f"{_DRAFT_DISCLAIMER}\n\n{best.chunk_text.strip()}"

        source_article_ids = list(dict.fromkeys(c.article_id for c in grounded_chunks))
        return ResolutionDraft(reply_text=reply_text, source_article_ids=source_article_ids)
