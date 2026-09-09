import json

from groq import Groq

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


class GroqLLMProvider:
    """Free-tier real LLM backend (Groq hosts open-weight models like Llama at no
    cost for this kind of usage). Same contract as AnthropicLLMProvider: both methods
    raise on any failure so the existing callers' fallback/retry logic handles it --
    classify_ticket falls back to the rule-based classifier, generate_suggestion falls
    back to MockLLMProvider. Mirrors the same grounding threshold and prompt template
    as every other provider, so swapping providers never changes the hallucination
    story.
    """

    def __init__(self, api_key: str, classify_model: str, resolution_model: str):
        self._client = Groq(api_key=api_key)
        self._classify_model = classify_model
        self._resolution_model = resolution_model

    def classify(self, subject: str, body: str) -> ClassificationResult:
        response = self._client.chat.completions.create(
            model=self._classify_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    # Ticket content is untrusted user data; the system prompt (not
                    # this user turn) defines the model's behavior/output shape.
                    "content": f"<ticket>\nSubject: {subject}\n\nBody: {body}\n</ticket>",
                },
            ],
        )
        data = json.loads(response.choices[0].message.content)
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
        response = self._client.chat.completions.create(
            model=self._resolution_model,
            messages=[{"role": "user", "content": prompt}],
        )
        reply_text = response.choices[0].message.content
        source_article_ids = list(dict.fromkeys(c.article_id for c in grounded_chunks))
        return ResolutionDraft(reply_text=reply_text, source_article_ids=source_article_ids)
