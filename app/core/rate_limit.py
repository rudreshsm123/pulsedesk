import ssl
import time

import redis.asyncio as redis
from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger("pulsedesk.rate_limit")

# Connection/socket timeouts are kept short and deliberately fail-open (see below) --
# rate limiting is a protective best-effort layer, not a correctness guarantee, so a
# Redis outage should degrade to "unlimited" rather than take the whole API down with it.
# Without this, a rediss:// URL (managed Redis over TLS, e.g. Upstash in the live
# deployment) would fail cert verification against Render's CA bundle and silently
# fail open on every request instead of actually rate limiting -- see
# app/workers/celery_app.py for the same tradeoff applied to Celery's Redis backend.
_is_tls_redis = settings.redis_url.startswith("rediss://")
_redis_kwargs = {"ssl_cert_reqs": ssl.CERT_NONE} if _is_tls_redis else {}

_redis_client = redis.from_url(
    settings.redis_url,
    socket_connect_timeout=0.3,
    socket_timeout=0.3,
    decode_responses=True,
    **_redis_kwargs,
)

# Atomic token-bucket refill+consume in a single round trip, keyed per caller.
_TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_per_second = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call("HMGET", key, "tokens", "timestamp")
local tokens = tonumber(bucket[1])
local timestamp = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    timestamp = now
end

local elapsed = math.max(0, now - timestamp)
tokens = math.min(capacity, tokens + elapsed * refill_per_second)

local allowed = 0
if tokens >= 1 then
    allowed = 1
    tokens = tokens - 1
end

redis.call("HMSET", key, "tokens", tokens, "timestamp", now)
redis.call("EXPIRE", key, 3600)

return allowed
"""


class TokenBucketRateLimiter:
    def __init__(self, capacity: int, refill_per_second: float):
        self._capacity = capacity
        self._refill_per_second = refill_per_second

    async def allow(self, key: str) -> bool:
        try:
            result = await _redis_client.eval(
                _TOKEN_BUCKET_SCRIPT,
                1,
                key,
                self._capacity,
                self._refill_per_second,
                time.time(),
            )
            return bool(result)
        except redis.RedisError:
            logger.warning(f"Redis unavailable for rate limiting on key={key}; failing open")
            return True


def rate_limit(key_prefix: str, capacity: int = 60, per_minute: int | None = None):
    refill_per_second = (per_minute or settings.rate_limit_per_minute) / 60
    limiter = TokenBucketRateLimiter(capacity=capacity, refill_per_second=refill_per_second)

    async def dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{key_prefix}:{client_ip}"

        if not await limiter.allow(key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests, please slow down",
            )

    return dependency
