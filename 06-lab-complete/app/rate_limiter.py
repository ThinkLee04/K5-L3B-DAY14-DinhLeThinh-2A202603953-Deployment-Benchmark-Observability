"""Atomic Redis sliding window per API key."""

from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException

from .config import settings
from .redis_client import r

WINDOW_SECONDS = 60

# Use Redis time so all workers measure the same window. A positive result is
# the number of seconds until another request can be accepted.
take_slot = r.register_script("""
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local clock = redis.call('TIME')
local now = clock[1] * 1000000 + clock[2]
local cutoff = now - window * 1000000

redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
if redis.call('ZCARD', key) >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    if #oldest == 0 then
        return window
    end
    return math.ceil((tonumber(oldest[2]) - cutoff) / 1000000)
end
redis.call('ZADD', key, now, ARGV[3])
redis.call('EXPIRE', key, window)
return 0
""")


def check_rate_limit(key: str) -> None:
    key_digest = sha256(key.encode()).hexdigest()
    retry_after = take_slot(
        keys=[f"agent:{settings.environment}:rate:{key_digest}"],
        args=[settings.rate_limit_per_minute, WINDOW_SECONDS, uuid4().hex],
    )
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
