import asyncio
import os
from uuid import uuid4

from argon2 import PasswordHasher
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import async_postgres_url, get_database_session
from app.main import app
from app.models import User


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for registration integration tests")
    return value


def test_registration_persists_exactly_one_hashed_user_and_rejects_duplicate() -> None:
    engine = create_async_engine(
        async_postgres_url(database_url()),
        poolclass=NullPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    email = f"registration-{uuid4()}@example.com"
    password = "correct-horse"

    async def override_session():
        async with sessions() as session:
            yield session

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

    async def cleanup() -> None:
        async with sessions() as session:
            await session.execute(delete(User).where(User.email == email))
            await session.commit()
        await engine.dispose()

    app.dependency_overrides[get_database_session] = override_session
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

        count, password_hash = asyncio.run(inspect_user())
        assert created.status_code == 201
        assert created.json()["email"] == email
        assert "password" not in created.text
        assert "hash" not in created.text
        assert count == 1
        assert password_hash != password
        assert PasswordHasher().verify(password_hash, password) is True
        assert duplicate.status_code == 409
    finally:
        app.dependency_overrides.clear()
        asyncio.run(cleanup())
