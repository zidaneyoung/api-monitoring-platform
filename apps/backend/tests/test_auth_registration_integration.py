import asyncio
import os
from uuid import uuid4

from argon2 import PasswordHasher
from fastapi.testclient import TestClient
import pytest
from redis.asyncio import from_url
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import async_postgres_url, get_database_session
from app.main import app
from app.models import User
from app.security.sessions import SessionStore, get_session_store, session_key


def required_url(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        pytest.skip(f"{name} is required for registration integration tests")
    return value


def test_registration_persists_exactly_one_hashed_user_and_rejects_duplicate() -> None:
    engine = create_async_engine(
        async_postgres_url(required_url("TEST_DATABASE_URL")),
        poolclass=NullPool,
    )
    redis_url = required_url("TEST_REDIS_URL")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    email = f"registration-{uuid4()}@example.com"
    password = "correct-horse"

    async def override_session():
        async with sessions() as session:
            yield session

    async def override_store():
        redis = from_url(redis_url, decode_responses=True)
        try:
            yield SessionStore(redis, ttl_seconds=3600)
        finally:
            await redis.aclose()

    async def inspect_user() -> tuple[int, str]:
        async with sessions() as session:
            count = await session.scalar(
                select(func.count()).select_from(User).where(User.email == email)
            )
            password_hash = await session.scalar(
                select(User.password_hash).where(User.email == email)
            )
            assert password_hash is not None
            return int(count or 0), password_hash

    async def inspect_session(token: str) -> tuple[str | None, int]:
        redis = from_url(redis_url, decode_responses=True)
        try:
            key = session_key(token)
            return await redis.get(key), await redis.ttl(key)
        finally:
            await redis.aclose()

    async def cleanup(token: str) -> None:
        redis = from_url(redis_url, decode_responses=True)
        try:
            if token:
                await redis.delete(session_key(token))
        finally:
            await redis.aclose()
        async with sessions() as session:
            await session.execute(delete(User).where(User.email == email))
            await session.commit()
        await engine.dispose()

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_session_store] = override_store
    token = ""
    try:
        with TestClient(app) as client:
            created = client.post(
                "/auth/register",
                json={"email": email.upper(), "password": password},
            )
            duplicate = client.post(
                "/auth/register",
                json={"email": email, "password": password},
            )

        token = created.cookies["amp_session"]
        count, password_hash = asyncio.run(inspect_user())
        stored_user_id, session_ttl = asyncio.run(inspect_session(token))
        assert created.status_code == 201
        assert created.json()["email"] == email
        assert "password" not in created.text
        assert "hash" not in created.text
        assert count == 1
        assert password_hash != password
        assert PasswordHasher().verify(password_hash, password) is True
        assert stored_user_id == created.json()["id"]
        assert 0 < session_ttl <= 3600
        assert created.headers["cache-control"] == "no-store"
        assert "amp_session" not in duplicate.cookies
        assert duplicate.status_code == 409
    finally:
        app.dependency_overrides.clear()
        asyncio.run(cleanup(token))
