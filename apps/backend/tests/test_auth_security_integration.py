import asyncio
from datetime import UTC, datetime
import os
from urllib.parse import urlparse
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from fastapi.testclient import TestClient
import pytest
from redis.asyncio import from_url
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import load_settings
from app.database import async_postgres_url, get_database_session
from app.main import app
from app.models import User
from app.security.sessions import SessionStore, get_session_store, session_key


def required_test_url(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        pytest.skip(f"{name} is required for authentication security integration tests")
    return value


def redis_target(value: str) -> tuple[str | None, int, str]:
    parsed = urlparse(value)
    return parsed.hostname, parsed.port or 6379, parsed.path.lstrip("/") or "0"


def database_target(value: str) -> tuple[str | None, int, str | None]:
    parsed = make_url(async_postgres_url(value))
    return parsed.host, parsed.port or 5432, parsed.database


def assert_isolated_test_services(database_url: str, redis_url: str) -> None:
    settings = load_settings()
    if database_target(database_url) == database_target(settings.database_url):
        pytest.fail("TEST_DATABASE_URL must not target the application database")
    if redis_target(redis_url) == redis_target(settings.redis_url):
        pytest.fail("TEST_REDIS_URL must not target the application Redis database")


def test_complete_authentication_lifecycle_and_current_user_isolation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    database_url = required_test_url("TEST_DATABASE_URL")
    redis_url = required_test_url("TEST_REDIS_URL")
    assert_isolated_test_services(database_url, redis_url)

    engine = create_async_engine(
        async_postgres_url(database_url),
        poolclass=NullPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    test_id = uuid4()
    emails = {
        "alpha": f"security-alpha-{test_id}@example.com",
        "beta": f"security-beta-{test_id}@example.com",
        "disabled": f"security-disabled-{test_id}@example.com",
    }
    passwords = {
        "alpha": "alpha-correct-horse",
        "beta": "beta-correct-horse",
        "disabled": "disabled-correct-horse",
    }
    session_tokens: list[str] = []
    previous_database_override = app.dependency_overrides.get(get_database_session)
    previous_session_override = app.dependency_overrides.get(get_session_store)

    async def override_database():
        async with sessions() as session:
            yield session

    async def override_session_store():
        redis = from_url(redis_url, decode_responses=True)
        try:
            yield SessionStore(redis, ttl_seconds=60)
        finally:
            await redis.aclose()

    async def disable_user_and_read_records() -> dict[str, tuple[UUID, str]]:
        async with sessions() as session:
            result = await session.execute(
                select(User).where(User.email.in_(emails.values()))
            )
            users = {user.email: user for user in result.scalars()}
            disabled_user = users[emails["disabled"]]
            disabled_user.is_active = False
            disabled_user.disabled_at = datetime.now(UTC)
            await session.commit()
            return {
                name: (users[email].id, users[email].password_hash)
                for name, email in emails.items()
            }

    async def expire_session(token: str) -> None:
        redis = from_url(redis_url, decode_responses=True)
        try:
            expired = await redis.expire(session_key(token), 0)
            assert expired is True
        finally:
            await redis.aclose()

    async def inspect_session(token: str) -> tuple[str | None, str]:
        redis = from_url(redis_url, decode_responses=True)
        key = session_key(token)
        try:
            return await redis.get(key), key
        finally:
            await redis.aclose()

    async def cleanup() -> None:
        redis = from_url(redis_url, decode_responses=True)
        try:
            keys = [session_key(token) for token in session_tokens]
            if keys:
                await redis.delete(*keys)
        finally:
            await redis.aclose()
            try:
                async with sessions() as session:
                    await session.execute(
                        delete(User).where(User.email.in_(emails.values()))
                    )
                    await session.commit()
            finally:
                await engine.dispose()

    app.dependency_overrides[get_database_session] = override_database
    app.dependency_overrides[get_session_store] = override_session_store
    try:
        with TestClient(app) as public_client:
            registrations = {
                name: public_client.post(
                    "/auth/register",
                    json={"email": email.upper(), "password": passwords[name]},
                )
                for name, email in emails.items()
            }
            duplicate_registration = public_client.post(
                "/auth/register",
                json={"email": emails["alpha"], "password": passwords["alpha"]},
            )
            invalid_registration = public_client.post(
                "/auth/register",
                json={"email": "invalid-email", "password": "short"},
            )

        records = asyncio.run(disable_user_and_read_records())
        alpha_id, alpha_hash = records["alpha"]
        beta_id, beta_hash = records["beta"]
        _, disabled_hash = records["disabled"]

        with TestClient(app) as unauthenticated_client:
            wrong_password = unauthenticated_client.post(
                "/auth/login",
                json={"email": emails["alpha"], "password": "wrong-password"},
            )
            nonexistent_user = unauthenticated_client.post(
                "/auth/login",
                json={
                    "email": f"missing-{test_id}@example.com",
                    "password": "wrong-password",
                },
            )
            disabled_user = unauthenticated_client.post(
                "/auth/login",
                json={
                    "email": emails["disabled"],
                    "password": passwords["disabled"],
                },
            )
            anonymous_current_user = unauthenticated_client.get("/auth/me")

        with TestClient(app) as alpha_client:
            alpha_login = alpha_client.post(
                "/auth/login",
                json={"email": emails["alpha"].upper(), "password": passwords["alpha"]},
            )
            alpha_token = alpha_login.cookies["amp_session"]
            session_tokens.append(alpha_token)
            alpha_navigation = alpha_client.get("/auth/me")
            alpha_refresh = alpha_client.get("/auth/me")
            alpha_cross_user_query = alpha_client.get(
                f"/auth/me?user_id={beta_id}"
            )
        alpha_session_value, alpha_session_key = asyncio.run(
            inspect_session(alpha_token)
        )

        with TestClient(app) as beta_client:
            beta_login = beta_client.post(
                "/auth/login",
                json={"email": emails["beta"], "password": passwords["beta"]},
            )
            beta_token = beta_login.cookies["amp_session"]
            session_tokens.append(beta_token)
            beta_current_user = beta_client.get(
                f"/auth/me?user_id={alpha_id}"
            )
            beta_session_value, beta_session_key = asyncio.run(
                inspect_session(beta_token)
            )
            beta_logout = beta_client.post("/auth/logout")
            beta_client.cookies.set("amp_session", beta_token)
            beta_replay = beta_client.get("/auth/me")

        with TestClient(app) as alpha_after_beta_logout:
            alpha_after_beta_logout.cookies.set("amp_session", alpha_token)
            alpha_still_authenticated = alpha_after_beta_logout.get("/auth/me")
            asyncio.run(expire_session(alpha_token))
            alpha_expired = alpha_after_beta_logout.get("/auth/me")

        assert [response.status_code for response in registrations.values()] == [
            201,
            201,
            201,
        ]
        assert duplicate_registration.status_code == 409
        assert invalid_registration.status_code == 422
        assert wrong_password.status_code == 401
        assert nonexistent_user.status_code == 401
        assert disabled_user.status_code == 401
        assert wrong_password.json() == nonexistent_user.json() == disabled_user.json()
        assert wrong_password.json()["detail"]["code"] == "invalid_credentials"

        assert alpha_login.status_code == 200
        assert beta_login.status_code == 200
        assert alpha_navigation.status_code == 200
        assert alpha_refresh.status_code == 200
        assert alpha_navigation.json() == alpha_refresh.json()
        assert alpha_cross_user_query.status_code == 200
        assert beta_current_user.status_code == 200
        assert alpha_cross_user_query.json() == {
            "id": str(alpha_id),
            "email": emails["alpha"],
        }
        assert beta_current_user.json() == {
            "id": str(beta_id),
            "email": emails["beta"],
        }
        assert alpha_cross_user_query.json() != beta_current_user.json()

        assert beta_logout.status_code == 204
        assert beta_replay.status_code == 401
        assert alpha_still_authenticated.status_code == 200
        assert alpha_still_authenticated.json()["id"] == str(alpha_id)
        assert alpha_expired.status_code == 401
        assert anonymous_current_user.status_code == 401
        assert alpha_session_value == str(alpha_id)
        assert beta_session_value == str(beta_id)

        assert PasswordHasher().verify(alpha_hash, passwords["alpha"])
        assert PasswordHasher().verify(beta_hash, passwords["beta"])
        assert PasswordHasher().verify(disabled_hash, passwords["disabled"])
        public_user_responses = [
            *registrations.values(),
            alpha_login,
            beta_login,
            alpha_navigation,
            alpha_refresh,
            alpha_cross_user_query,
            beta_current_user,
            alpha_still_authenticated,
        ]
        sensitive_values = [
            *passwords.values(),
            alpha_hash,
            beta_hash,
            disabled_hash,
            alpha_token,
            beta_token,
            "wrong-password",
            "short",
        ]
        for response in public_user_responses:
            assert set(response.json()) == {"id", "email"}
            assert "password" not in response.text
            assert "hash" not in response.text
            for sensitive_value in sensitive_values:
                assert sensitive_value not in response.text

        error_responses = [
            duplicate_registration,
            invalid_registration,
            wrong_password,
            nonexistent_user,
            disabled_user,
            anonymous_current_user,
            beta_replay,
            alpha_expired,
        ]
        for response in error_responses:
            for sensitive_value in sensitive_values:
                assert sensitive_value not in response.text

        for sensitive_value in sensitive_values:
            assert sensitive_value not in caplog.text
            assert sensitive_value not in alpha_session_key
            assert sensitive_value not in beta_session_key
    finally:
        if previous_database_override is None:
            app.dependency_overrides.pop(get_database_session, None)
        else:
            app.dependency_overrides[get_database_session] = previous_database_override
        if previous_session_override is None:
            app.dependency_overrides.pop(get_session_store, None)
        else:
            app.dependency_overrides[get_session_store] = previous_session_override
        asyncio.run(cleanup())
