import asyncio
import os
from uuid import uuid4

import pytest
from redis.asyncio import from_url

from app.security.sessions import SessionStore, session_key


def redis_url() -> str:
    value = os.getenv("TEST_REDIS_URL")
    if value is None:
        pytest.skip("TEST_REDIS_URL is required for session integration tests")
    return value


def test_session_is_shared_renewed_and_rejected_after_expiration() -> None:
    async def exercise_session() -> None:
        first_redis = from_url(redis_url(), decode_responses=True)
        second_redis = from_url(redis_url(), decode_responses=True)
        first_store = SessionStore(first_redis, ttl_seconds=60)
        second_store = SessionStore(second_redis, ttl_seconds=60)
        user_id = uuid4()
        token = await first_store.create_session(user_id)
        key = session_key(token)
        try:
            await first_redis.expire(key, 5)
            resolved_user_id = await second_store.get_user_id(token, renew=True)
            renewed_ttl = await first_redis.ttl(key)
            invalid_user_id = await second_store.get_user_id(
                "invalid-session",
                renew=True,
            )

            await first_redis.expire(key, 0)
            expired_user_id = await second_store.get_user_id(token, renew=True)

            assert resolved_user_id == user_id
            assert 50 <= renewed_ttl <= 60
            assert invalid_user_id is None
            assert expired_user_id is None
            assert token not in key
        finally:
            await first_redis.delete(key)
            await first_redis.aclose()
            await second_redis.aclose()

    asyncio.run(exercise_session())
