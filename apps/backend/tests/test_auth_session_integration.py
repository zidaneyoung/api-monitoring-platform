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


def test_logout_deletes_only_the_selected_session() -> None:
    async def exercise_logout() -> None:
        redis = from_url(redis_url(), decode_responses=True)
        store = SessionStore(redis, ttl_seconds=60)
        first_user_id = uuid4()
        second_user_id = uuid4()
        first_token = await store.create_session(first_user_id)
        second_token = await store.create_session(second_user_id)
        try:
            await store.delete_session(first_token)

            assert await store.get_user_id(first_token, renew=False) is None
            assert await store.get_user_id(second_token, renew=False) == second_user_id
        finally:
            await redis.delete(session_key(first_token), session_key(second_token))
            await redis.aclose()

    asyncio.run(exercise_logout())
