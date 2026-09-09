import json

from anthropic import Anthropic

from app.core.enums import TicketPriority
from app.services.llm.base import (
    NO_GROUNDING_REPLY,
    SIMILARITY_THRESHOLD,
    ClassificationResult,
    ResolutionDraft,
    RetrievedChunk,
    build_grounded_prompt,
)

_CLASSIFY_SYSTEM_PROMPT = (
    "You triage customer support tickets. Read the subject and body and respond with "
    "ONLY a JSON object of the exact shape "
    '{"category": <short lowercase category>, "priority": "LOW"|"MEDIUM"|"HIGH"|"URGENT", '
    '"confidence": <number between 0 and 1>}. No other text, no markdown fences.'
)


class AnthropicLLMProvider:
    """Real LLM backend. classify() and generate_resolution() both raise on any
    failure (network error, malformed JSON, bad enum value) rather than swallowing it --
    callers (app/workers/classify.py, app/workers/rag_suggest.py) already handle that:
    classify_ticket falls back to the rule-based classifier, and generate_suggestion's
    Celery task retries with backoff via autoretry_for. Mirroring MockLLMProvider's
    threshold/grounding behavior here (not delegating resolution drafting entirely to
    the model's judgment) is deliberate: it's a second, code-level guarantee against
    hallucination that doesn't depend on the model reliably following the prompt.
    """

    def __init__(
        self,
        api_key: str,
        classify_model: str,
        resolution_model: str,
    ):
        self._client = Anthropic(api_key=api_key)
        self._classify_model = classify_model
        self._resolution_model = resolution_model

    def classify(self, subject: str, body: str) -> ClassificationResult:
        response = self._client.messages.create(
            model=self._classify_model,
            max_tokens=200,
            system=_CLASSIFY_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    # Ticket content is untrusted user data; the system prompt (not this
                    # user turn) is what defines the model's behavior/output shape, so
                    # ticket text has no channel to redefine its own handling.
                    "content": f"<ticket>\nSubject: {subject}\n\nBody: {body}\n</ticket>",
                }
            ],
        )
        data = json.loads(response.content[0].text)
        return ClassificationResult(
            category=str(data["category"]),
            priority=TicketPriority(str(data["priority"]).upper()),
            confidence=float(data["confidence"]),
        )

    def generate_resolution(
        self, ticket_text: str, retrieved_chunks: list[RetrievedChunk]
    ) -> ResolutionDraft:
        grounded_chunks = [c for c in retrieved_chunks if c.similarity >= SIMILARITY_THRESHOLD]
        if not grounded_chunks:
            return ResolutionDraft(reply_text=NO_GROUNDING_REPLY, source_article_ids=[])

        prompt = build_grounded_prompt(ticket_text, grounded_chunks)
        response = self._client.messages.create(
            model=self._resolution_model,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        reply_text = response.content[0].text
        source_article_ids = list(dict.fromkeys(c.article_id for c in grounded_chunks))
        return ResolutionDraft(reply_text=reply_text, source_article_ids=source_article_ids)
