from functools import lru_cache

from app.core.config import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.mock_provider import MockLLMProvider

settings = get_settings()


@lru_cache
def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "anthropic":
        if not settings.llm_api_key:
            raise RuntimeError("LLM_PROVIDER=anthropic requires LLM_API_KEY to be set")

        from app.services.llm.anthropic_provider import AnthropicLLMProvider

        return AnthropicLLMProvider(
            api_key=settings.llm_api_key,
            classify_model=settings.llm_classify_model,
            resolution_model=settings.llm_resolution_model,
        )

    return MockLLMProvider()
