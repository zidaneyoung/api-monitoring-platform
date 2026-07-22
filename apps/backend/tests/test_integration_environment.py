import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from redis.asyncio import from_url
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.config import load_settings
from app.database import async_postgres_url, create_database_engine


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TABLES = {
    "users",
    "monitors",
    "monitor_runs",
    "monitor_checks",
    "incidents",
    "incident_events",
    "notification_deliveries",
}


def required_url(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        pytest.skip(f"{name} is required for integration environment tests")
    return value


def database_target(value: str) -> tuple[str | None, int, str | None]:
    parsed = make_url(async_postgres_url(value))
    return parsed.host, parsed.port or 5432, parsed.database


def redis_target(value: str) -> tuple[str | None, int, str]:
    parsed = urlparse(value)
    return parsed.hostname, parsed.port or 6379, parsed.path.lstrip("/") or "0"


def test_postgres_redis_and_configuration_are_isolated() -> None:
    database_url = required_url("TEST_DATABASE_URL")
    redis_url = required_url("TEST_REDIS_URL")
    settings = load_settings()

    assert os.getenv("ENVIRONMENT") == "test"
    assert database_target(database_url) != database_target(settings.database_url)
    assert redis_target(redis_url) != redis_target(settings.redis_url)
    assert "integration" in (database_target(database_url)[2] or "")
    assert redis_target(redis_url)[2] == "15"

    async def probe() -> None:
        engine = create_database_engine(database_url)
        redis = from_url(redis_url, decode_responses=True)
        try:
            async with engine.connect() as connection:
                assert await connection.scalar(text("SELECT current_database()")) == (
                    database_target(database_url)[2]
                )
            assert await redis.ping() is True
        finally:
            await redis.aclose()
            await engine.dispose()

    asyncio.run(probe())


def test_alembic_is_at_head_and_required_tables_exist() -> None:
    database_url = required_url("TEST_DATABASE_URL")
    scripts = ScriptDirectory.from_config(Config(str(BACKEND_ROOT / "alembic.ini")))

    async def inspect_schema() -> None:
        engine = create_database_engine(database_url)
        try:
            async with engine.connect() as connection:
                current_revision = await connection.scalar(
                    text("SELECT version_num FROM alembic_version")
                )
                table_names = set(
                    (
                        await connection.scalars(
                            text(
                                "SELECT tablename FROM pg_tables "
                                "WHERE schemaname = 'public'"
                            )
                        )
                    ).all()
                )
            assert current_revision == scripts.get_current_head()
            assert REQUIRED_TABLES <= table_names
        finally:
            await engine.dispose()

    asyncio.run(inspect_schema())
