import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PGVECTOR_IMAGE = "pgvector/pgvector:pg16"


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer(PGVECTOR_IMAGE, driver="asyncpg") as container:
        yield container


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session", autouse=True)
def _run_migrations(database_url: str) -> None:
    # migrations/env.py resolves its DB URL through the app's Settings (env-var backed,
    # lru_cache'd), so the simplest way to point Alembic at this ephemeral container
    # without fighting that cache from inside the test process is to run it as a fresh
    # subprocess with DATABASE_URL overridden for just that subprocess.
    env = {**os.environ, "DATABASE_URL": database_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env=env,
        cwd=str(PROJECT_ROOT),
    )


@pytest_asyncio.fixture
async def db_session(database_url: str) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()
