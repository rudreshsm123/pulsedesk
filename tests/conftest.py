import os

# Must run before any `app.*` module is imported anywhere in the test session --
# app.core.config.get_settings() is lru_cache'd, and Settings reads LLM_PROVIDER /
# LLM_API_KEY from the developer's real .env. Without this override, a developer who
# sets LLM_PROVIDER=anthropic locally (to actually use the real provider) would have
# their test suite silently start making real, billed network calls -- pytest's
# collection order guarantees this file loads before any test module's imports, so
# setting the env var here reliably wins the race against get_settings()'s first call.
os.environ["LLM_PROVIDER"] = "mock"
