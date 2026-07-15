import asyncio
import os

import pytest
from sqlalchemy import text

from app.database import create_database_engine


def test_postgres_executes_select_one() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is required for the PostgreSQL integration test")

    async def execute_query() -> None:
        engine = create_database_engine(database_url)
        try:
            async with engine.connect() as connection:
                assert await connection.scalar(text("SELECT 1")) == 1
        finally:
            await engine.dispose()

    asyncio.run(execute_query())
