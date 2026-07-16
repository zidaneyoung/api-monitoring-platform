from dataclasses import dataclass
from hashlib import sha256
import hmac
from typing import Literal

from redis.asyncio import Redis, from_url
from redis.exceptions import RedisError

from app.config import load_settings


RateLimitScope = Literal["login", "register"]
RateLimitDimension = Literal["source", "account", "source-account"]


class RateLimitStoreUnavailableError(RuntimeError):
    """Raised without Redis details when rate-limit state cannot be enforced."""


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    attempts: int
    retry_after: int


_CONSUME_SCRIPT = """
local limit = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2]) * 1000
local attempts = tonumber(redis.call('GET', KEYS[1]) or '0')
local ttl_ms = redis.call('PTTL', KEYS[1])

if ttl_ms <= 0 then
  redis.call('DEL', KEYS[1])
  attempts = 0
  ttl_ms = 0
end

if attempts >= limit then
  return {0, attempts, math.max(1, math.ceil(ttl_ms / 1000))}
end

attempts = redis.call('INCR', KEYS[1])
if attempts == 1 then
  redis.call('PEXPIRE', KEYS[1], window_ms)
  ttl_ms = window_ms
else
  ttl_ms = redis.call('PTTL', KEYS[1])
end

return {1, attempts, math.max(1, math.ceil(ttl_ms / 1000))}
"""


def rate_limit_key(
    scope: RateLimitScope,
    dimension: RateLimitDimension,
    identifier: str,
    secret: str,
) -> str:
    identifier_digest = hmac.new(
        secret.encode("utf-8"),
        f"{scope}:{dimension}:{identifier}".encode("utf-8"),
        sha256,
    ).hexdigest()
    return f"auth:rate:{scope}:{dimension}:{identifier_digest}"


def rate_limit_keys(
    scope: RateLimitScope,
    source_identifier: str,
    account_identifier: str,
    secret: str,
) -> tuple[str, str, str]:
    return (
        rate_limit_key(scope, "source", source_identifier, secret),
        rate_limit_key(scope, "account", account_identifier, secret),
        rate_limit_key(
            scope,
            "source-account",
            f"{source_identifier}\0{account_identifier}",
            secret,
        ),
    )


class RateLimitStore:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def consume(
        self,
        key: str,
        *,
        max_attempts: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        try:
            result = await self.redis.eval(
                _CONSUME_SCRIPT,
                1,
                key,
                max_attempts,
                window_seconds,
            )
            allowed, attempts, retry_after = result
            return RateLimitDecision(
                allowed=bool(int(allowed)),
                attempts=int(attempts),
                retry_after=max(1, int(retry_after)),
            )
        except (RedisError, TypeError, ValueError):
            raise RateLimitStoreUnavailableError(
                "Rate-limit service unavailable"
            ) from None


_settings = load_settings()
_redis = from_url(_settings.redis_url, decode_responses=True)
_rate_limit_store = RateLimitStore(_redis)


async def get_rate_limit_store() -> RateLimitStore:
    return _rate_limit_store


async def close_rate_limit_store() -> None:
    await _redis.aclose()
