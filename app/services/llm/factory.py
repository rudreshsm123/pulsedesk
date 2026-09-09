from functools import lru_cache

from app.core.config import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.mock_provider import MockLLMProvider

settings = get_settings()

# (classify_model, resolution_model) defaults per provider -- these are provider-
# specific (an Anthropic model name is meaningless to Groq's API and vice versa), so
# they live here rather than as a single generic default on Settings.
_DEFAULT_MODELS = {
    "anthropic": ("claude-haiku-4-5-20251001", "claude-sonnet-5"),
    # Groq's hosted-model catalog rotates faster than most providers' (models get
    # deprecated/replaced); verified live against the account's actual /models list
    # rather than assumed, since the previously-documented llama-3.x names had already
    # been retired by the time this was tested end to end.
    "groq": ("openai/gpt-oss-20b", "openai/gpt-oss-120b"),
}


@lru_cache
def get_llm_provider() -> LLMProvider:
    provider = settings.llm_provider

    if provider in _DEFAULT_MODELS:
        if not settings.llm_api_key:
            raise RuntimeError(f"LLM_PROVIDER={provider} requires LLM_API_KEY to be set")

        default_classify_model, default_resolution_model = _DEFAULT_MODELS[provider]
        classify_model = settings.llm_classify_model or default_classify_model
        resolution_model = settings.llm_resolution_model or default_resolution_model

        if provider == "anthropic":
            from app.services.llm.anthropic_provider import AnthropicLLMProvider

            return AnthropicLLMProvider(
                api_key=settings.llm_api_key,
                classify_model=classify_model,
                resolution_model=resolution_model,
            )

        from app.services.llm.groq_provider import GroqLLMProvider

        return GroqLLMProvider(
            api_key=settings.llm_api_key,
            classify_model=classify_model,
            resolution_model=resolution_model,
        )

    return MockLLMProvider()
