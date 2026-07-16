import asyncio
from datetime import UTC, datetime
import json
import os
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from redis.asyncio import from_url
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import async_postgres_url, get_database_session
from app.main import app
from app.models import User
from app.security.passwords import hash_password
from app.security.sessions import SessionStore, get_session_store, session_key


def required_url(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        pytest.skip(f"{name} is required for login integration tests")
    return value


def test_login_verifies_persisted_hash_and_creates_shared_session() -> None:
    database_url = required_url("TEST_DATABASE_URL")
    redis_url = required_url("TEST_REDIS_URL")
    engine = create_async_engine(async_postgres_url(database_url), poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid4()
    email = f"login-{user_id}@example.com"
    password = "correct-horse"
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        email=email,
        password_hash=hash_password(password),
        is_active=True,
        disabled_at=None,
        created_at=now,
        updated_at=now,
    )

    async def setup() -> None:
        async with sessions() as session:
            session.add(user)
            await session.commit()

    async def override_session():
        async with sessions() as session:
            yield session

    async def override_store():
        redis = from_url(redis_url, decode_responses=True)
        try:
            yield SessionStore(redis, ttl_seconds=3600)
        finally:
            await redis.aclose()

    async def inspect_and_cleanup(token: str) -> tuple[dict[str, object] | None, int]:
        redis = from_url(redis_url, decode_responses=True)
        key = session_key(token)
        try:
            value = await redis.get(key)
            stored_session = json.loads(value) if value is not None else None
            ttl = await redis.ttl(key)
            await redis.delete(key)
        finally:
            await redis.aclose()

        async with sessions() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()
        return stored_session, ttl

    asyncio.run(setup())
    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_session_store] = override_store
    token = ""
    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/login",
                json={"email": email.upper(), "password": password},
            )
        token = response.cookies["amp_session"]
        stored_session, ttl = asyncio.run(inspect_and_cleanup(token))

        assert response.status_code == 200
        assert response.json() == {"id": str(user_id), "email": email}
        assert token not in response.text
        assert stored_session is not None
        assert stored_session["user_id"] == str(user_id)
        assert stored_session["created_at"] == stored_session["last_seen_at"]
        assert stored_session["idle_expires_at"] <= stored_session["absolute_expires_at"]
        assert 0 < ttl <= 3600
    finally:
        app.dependency_overrides.clear()
        if not token:
            asyncio.run(inspect_and_cleanup("missing-session"))
