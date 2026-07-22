import asyncio
import os
from urllib.parse import urlparse

from redis.asyncio import from_url
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.database import async_postgres_url, create_database_engine


def required_url(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def assert_isolated_targets(database_url: str, redis_url: str) -> None:
    database_name = make_url(async_postgres_url(database_url)).database or ""
    redis_database = urlparse(redis_url).path.lstrip("/") or "0"
    if not any(marker in database_name.lower() for marker in ("test", "integration")):
        raise RuntimeError("integration database name must identify a test target")
    if redis_database == "0":
        raise RuntimeError("integration Redis must use a non-default database")


async def prepare() -> None:
    database_url = required_url("TEST_DATABASE_URL")
    redis_url = required_url("TEST_REDIS_URL")
    assert_isolated_targets(database_url, redis_url)

    engine = create_database_engine(database_url)
    redis = from_url(redis_url, decode_responses=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE TABLE users CASCADE"))
        await redis.flushdb()
    finally:
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(prepare())
