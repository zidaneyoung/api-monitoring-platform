import asyncio
import os
from uuid import uuid4

import pytest
from redis.asyncio import from_url

from app.security.rate_limits import RateLimitStore, rate_limit_key


def redis_url() -> str:
    value = os.getenv("TEST_REDIS_URL")
    if value is None:
        pytest.skip("TEST_REDIS_URL is required for rate-limit integration tests")
    return value


def test_rate_limit_is_shared_and_allows_retry_after_natural_reset() -> None:
    async def exercise_rate_limit() -> None:
        first_redis = from_url(redis_url(), decode_responses=True)
        second_redis = from_url(redis_url(), decode_responses=True)
        first_store = RateLimitStore(first_redis)
        second_store = RateLimitStore(second_redis)
        raw_identity = f"198.51.100.17-{uuid4()}"
        key = rate_limit_key("login", raw_identity)
        try:
            first = await first_store.consume(
                key,
                max_attempts=2,
                window_seconds=1,
            )
            second = await second_store.consume(
                key,
                max_attempts=2,
                window_seconds=1,
            )
            blocked = await first_store.consume(
                key,
                max_attempts=2,
                window_seconds=1,
            )
            ttl = await second_redis.pttl(key)

            await asyncio.sleep(1.1)
            retry = await second_store.consume(
                key,
                max_attempts=2,
                window_seconds=1,
            )

            assert first.allowed is True and first.attempts == 1
            assert second.allowed is True and second.attempts == 2
            assert blocked.allowed is False and blocked.retry_after >= 1
            assert 0 < ttl <= 1000
            assert retry.allowed is True and retry.attempts == 1
            assert raw_identity not in key
        finally:
            await first_redis.delete(key)
            await first_redis.aclose()
            await second_redis.aclose()

    asyncio.run(exercise_rate_limit())
