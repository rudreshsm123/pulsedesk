import pytest
import redis.asyncio as redis

from app.core import rate_limit as rate_limit_module
from app.core.rate_limit import TokenBucketRateLimiter


@pytest.mark.asyncio
async def test_allows_request_when_tokens_available(monkeypatch):
    async def fake_eval(*args, **kwargs):
        return 1

    monkeypatch.setattr(rate_limit_module._redis_client, "eval", fake_eval)
    limiter = TokenBucketRateLimiter(capacity=5, refill_per_second=1)

    assert await limiter.allow("test-key") is True


@pytest.mark.asyncio
async def test_denies_request_when_bucket_empty(monkeypatch):
    async def fake_eval(*args, **kwargs):
        return 0

    monkeypatch.setattr(rate_limit_module._redis_client, "eval", fake_eval)
    limiter = TokenBucketRateLimiter(capacity=5, refill_per_second=1)

    assert await limiter.allow("test-key") is False


@pytest.mark.asyncio
async def test_fails_open_when_redis_unavailable(monkeypatch):
    async def raising_eval(*args, **kwargs):
        raise redis.RedisError("connection refused")

    monkeypatch.setattr(rate_limit_module._redis_client, "eval", raising_eval)
    limiter = TokenBucketRateLimiter(capacity=5, refill_per_second=1)

    # A Redis outage must not block traffic -- rate limiting is best-effort protection,
    # not a correctness guarantee (see the module docstring/comment for why).
    assert await limiter.allow("test-key") is True
