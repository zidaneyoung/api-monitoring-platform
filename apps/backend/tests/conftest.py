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
