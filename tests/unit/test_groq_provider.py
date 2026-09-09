import json
import uuid
from unittest.mock import MagicMock

import pytest

from app.core.enums import TicketPriority
from app.services.llm.base import NO_GROUNDING_REPLY, RetrievedChunk
from app.services.llm.groq_provider import GroqLLMProvider

# Mocks the Groq client itself (per docs/security.md's mock-vs-real rationale): no
# network calls, no API key needed.


def make_provider() -> GroqLLMProvider:
    return GroqLLMProvider(
        api_key="test-key", classify_model="test-classify-model", resolution_model="test-model"
    )


def fake_completion(text: str) -> MagicMock:
    completion = MagicMock()
    completion.choices = [MagicMock(message=MagicMock(content=text))]
    return completion


def test_classify_parses_json_response():
    provider = make_provider()
    provider._client = MagicMock()
    provider._client.chat.completions.create.return_value = fake_completion(
        json.dumps({"category": "billing", "priority": "HIGH", "confidence": 0.87})
    )

    result = provider.classify("Overcharged", "I was billed twice this month")

    assert result.category == "billing"
    assert result.priority == TicketPriority.HIGH
    assert result.confidence == 0.87
    call_kwargs = provider._client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "test-classify-model"
    assert call_kwargs["response_format"] == {"type": "json_object"}


def test_classify_raises_on_malformed_json_so_caller_can_fall_back():
    provider = make_provider()
    provider._client = MagicMock()
    provider._client.chat.completions.create.return_value = fake_completion("not json")

    with pytest.raises(json.JSONDecodeError):
        provider.classify("Subject", "Body")


def test_classify_raises_on_invalid_priority_value():
    provider = make_provider()
    provider._client = MagicMock()
    provider._client.chat.completions.create.return_value = fake_completion(
        json.dumps({"category": "billing", "priority": "SUPER_URGENT", "confidence": 0.5})
    )

    with pytest.raises(ValueError):
        provider.classify("Subject", "Body")


def test_generate_resolution_skips_the_api_call_when_nothing_is_grounded():
    provider = make_provider()
    provider._client = MagicMock()

    draft = provider.generate_resolution("ticket text", [])

    assert draft.reply_text == NO_GROUNDING_REPLY
    provider._client.chat.completions.create.assert_not_called()


def test_generate_resolution_calls_the_resolution_model_with_grounded_chunks():
    provider = make_provider()
    provider._client = MagicMock()
    provider._client.chat.completions.create.return_value = fake_completion(
        "Here is how to fix it."
    )
    article_id = uuid.uuid4()
    chunk = RetrievedChunk(article_id=article_id, chunk_text="Do the thing.", similarity=0.9)

    draft = provider.generate_resolution("How do I fix this?", [chunk])

    assert draft.reply_text == "Here is how to fix it."
    assert draft.source_article_ids == [article_id]
    call_kwargs = provider._client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "test-model"
    assert "<ticket>" in call_kwargs["messages"][0]["content"]
