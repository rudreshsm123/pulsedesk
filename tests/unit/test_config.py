from app.core.config import Settings


def test_settings_strips_trailing_newline_from_database_url():
    # Regression test: Render's env-var UI appended a trailing newline to a pasted
    # DATABASE_URL in production, which asyncpg then reported as the database named
    # "postgres\n" not existing -- a real deploy failure, not a hypothetical one.
    settings = Settings(database_url="postgresql+asyncpg://user:pass@host:5432/postgres\n")

    assert settings.database_url == "postgresql+asyncpg://user:pass@host:5432/postgres"


def test_settings_strips_whitespace_from_redis_url():
    settings = Settings(redis_url="  redis://localhost:6379/0  \n")

    assert settings.redis_url == "redis://localhost:6379/0"


def test_settings_strips_whitespace_from_secret_fields():
    settings = Settings(
        jwt_secret_key="my-secret-key-padded-to-32-bytes\n", llm_api_key="gsk_abc123\n"
    )

    assert settings.jwt_secret_key == "my-secret-key-padded-to-32-bytes"
    assert settings.llm_api_key == "gsk_abc123"


def test_settings_leaves_none_llm_api_key_unchanged():
    settings = Settings(llm_api_key=None)

    assert settings.llm_api_key is None
