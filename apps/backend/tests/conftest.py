import asyncio
import os

import pytest

import app.models  # noqa: F401
from app.database import Base, create_database_engine
from app.main import app
from app.security.rate_limits import (
    RateLimitDecision,
    get_rate_limit_store,
)


class AllowAllRateLimitStore:
    async def consume(
        self,
        _key: str,
        *,
        max_attempts: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        return RateLimitDecision(
            allowed=True,
            attempts=1,
            retry_after=window_seconds,
        )


@pytest.fixture
def production_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    values = {
        "AUTH_ALLOW_MISSING_ORIGIN": "false",
        "AUTH_RATE_LIMIT_KEY_SECRET": (
            "production-test-rate-limit-secret-0001"
        ),
        "CELERY_BROKER_URL": "redis://cache.example.test:6379/0",
        "CELERY_RESULT_BACKEND": "redis://cache.example.test:6379/0",
        "DATABASE_URL": (
            "postgresql+asyncpg://test-user:test-password@db.example.test/app"
        ),
        "DEBUG": "false",
        "EMAIL_FROM": "no-reply@example.test",
        "EMAIL_HOST": "smtp.example.test",
        "EMAIL_PASSWORD": "test-email-password",
        "EMAIL_PORT": "587",
        "EMAIL_USERNAME": "test-email-user",
        "EMAIL_USE_TLS": "true",
        "ENVIRONMENT": "production",
        "FRONTEND_ORIGIN": "https://app.example.test",
        "REDIS_URL": "redis://cache.example.test:6379/0",
        "SESSION_COOKIE_NAME": "amp_session",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return values


@pytest.fixture(autouse=True)
def isolate_auth_rate_limits():
    store = AllowAllRateLimitStore()

    async def override_store() -> AllowAllRateLimitStore:
        return store

    app.dependency_overrides[get_rate_limit_store] = override_store
    yield
    app.dependency_overrides.pop(get_rate_limit_store, None)


@pytest.fixture(scope="session", autouse=True)
def ensure_test_database_schema():
    """Bootstrap the schema needed by integration tests from a clean database."""

    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        yield
        return

    async def create_schema() -> None:
        engine = create_database_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        finally:
            await engine.dispose()

    asyncio.run(create_schema())
    yield
