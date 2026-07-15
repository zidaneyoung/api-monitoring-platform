import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app import database
from app.config import load_settings


class SessionContext:
    def __init__(self) -> None:
        self.session = AsyncMock()
        self.exited = False

    async def __aenter__(self) -> AsyncMock:
        return self.session

    async def __aexit__(self, *args: object) -> None:
        self.exited = True


def test_database_url_comes_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "postgresql+asyncpg://user:password@database:5432/app"
    monkeypatch.setenv("DATABASE_URL", database_url)

    assert load_settings().database_url == database_url


def test_engine_normalizes_postgresql_url_for_asyncpg() -> None:
    test_engine = database.create_database_engine(
        "postgresql://user:password@database:5432/app"
    )

    assert test_engine.url.drivername == "postgresql+asyncpg"
    asyncio.run(test_engine.dispose())


def test_session_dependency_releases_session(monkeypatch: pytest.MonkeyPatch) -> None:
    context = SessionContext()
    monkeypatch.setattr(database, "SessionFactory", lambda: context)

    async def consume_session() -> None:
        dependency = database.get_database_session()
        assert await anext(dependency) is context.session
        await dependency.aclose()

    asyncio.run(consume_session())

    assert context.exited is True


def test_session_dependency_rolls_back_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = SessionContext()
    monkeypatch.setattr(database, "SessionFactory", lambda: context)

    async def fail_request() -> None:
        dependency = database.get_database_session()
        await anext(dependency)
        with pytest.raises(RuntimeError, match="request failed"):
            await dependency.athrow(RuntimeError("request failed"))

    asyncio.run(fail_request())

    context.session.rollback.assert_awaited_once_with()
    assert context.exited is True


@pytest.mark.parametrize(
    "connection_error",
    [
        SQLAlchemyError(
            "postgresql://user:secret@database:5432/app connection failed"
        ),
        OSError("postgresql://user:secret@database:5432/app socket failed"),
    ],
)
def test_connection_error_hides_database_details(
    monkeypatch: pytest.MonkeyPatch,
    connection_error: Exception,
) -> None:
    class FailingConnection:
        async def __aenter__(self) -> None:
            raise connection_error

        async def __aexit__(self, *args: object) -> None:
            return None

    mock_engine = AsyncMock()
    mock_engine.connect = lambda: FailingConnection()
    monkeypatch.setattr(database, "engine", mock_engine)

    with pytest.raises(database.DatabaseUnavailableError) as error:
        asyncio.run(database.check_database_connection())

    assert str(error.value) == "Database unavailable"
    assert error.value.__cause__ is None
