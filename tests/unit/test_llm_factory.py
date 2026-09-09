from app.core.config import get_settings
from app.services.llm.factory import get_llm_provider
from app.services.llm.mock_provider import MockLLMProvider


def test_llm_provider_is_mock_during_tests_regardless_of_local_env():
    # Regression test for tests/conftest.py's LLM_PROVIDER override: a developer's
    # local .env may legitimately be set to "anthropic" to actually use the real
    # provider day-to-day, and the test suite must never silently make real, billed
    # API calls just because of that.
    assert get_settings().llm_provider == "mock"
    assert isinstance(get_llm_provider(), MockLLMProvider)
