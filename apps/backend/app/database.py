from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import load_settings


class DatabaseUnavailableError(RuntimeError):
    """Raised without connection details when PostgreSQL cannot be reached."""


def _async_postgres_url(database_url: str) -> URL:
    url = make_url(database_url)
    if url.drivername == "postgresql":
        return url.set(drivername="postgresql+asyncpg")
    if url.drivername != "postgresql+asyncpg":
        raise ValueError("DATABASE_URL must use PostgreSQL with the asyncpg driver")
    return url


def create_database_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        _async_postgres_url(database_url),
        pool_pre_ping=True,
    )


engine = create_database_engine(load_settings().database_url)
SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_database_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_database_connection() -> bool:
    try:
        async with engine.connect() as connection:
            return await connection.scalar(text("SELECT 1")) == 1
    except (SQLAlchemyError, OSError):
        raise DatabaseUnavailableError("Database unavailable") from None


async def dispose_database_engine() -> None:
    await engine.dispose()
