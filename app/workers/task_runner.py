import asyncio
from collections.abc import Coroutine

from app.core.db import engine


def run_task[T](coro: Coroutine[None, None, T]) -> T:
    """Runs a worker coroutine to completion and disposes the DB engine's connection
    pool before the event loop closes.

    Celery invokes each task body via asyncio.run(), which creates a brand-new event
    loop per call and destroys it on return. SQLAlchemy's async engine keeps a
    connection pool whose connections are bound to whatever loop created them -- if a
    pooled connection outlives its loop, the next task's asyncio.run() (a different
    loop) blows up trying to reuse or close it ("RuntimeError: Event loop is closed").
    Disposing the pool here, while this task's loop is still alive, guarantees every
    task starts against an empty pool instead of one holding a connection from a dead
    loop.
    """

    async def _wrapped() -> T:
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())
