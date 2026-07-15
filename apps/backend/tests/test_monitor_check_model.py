import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine
from app.models import Monitor, MonitorCheck, MonitorRun, User


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for database model tests")
    return value


async def create_monitor_and_run(
    sessions: async_sessionmaker,
) -> tuple[Monitor, MonitorRun]:
    async with sessions() as session:
        await session.execute(text("DELETE FROM users"))
        user = User(email="checks@example.com", password_hash="hash")
        monitor = Monitor(
            user=user,
            name="Check monitor",
            url="https://example.com",
            interval_seconds=60,
            timeout_seconds=10,
        )
        run = MonitorRun(
            monitor=monitor,
            scheduled_for=datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc),
        )
        session.add(run)
        await session.commit()
        await session.refresh(monitor)
        await session.refresh(run)
        return monitor, run


def test_monitor_check_success_relationships_tls_and_utc_timestamps() -> None:
    async def persist_check() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            monitor, run = await create_monitor_and_run(sessions)
            started_at = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)
            completed_at = started_at + timedelta(milliseconds=125)
            tls_expires_at = datetime(2026, 12, 1, tzinfo=timezone.utc)
            async with sessions() as session:
                check = MonitorCheck(
                    monitor_id=monitor.id,
                    run_id=run.id,
                    started_at=started_at,
                    completed_at=completed_at,
                    success=True,
                    response_time_ms=125,
                    http_status_code=200,
                    tls_expires_at=tls_expires_at,
                )
                session.add(check)
                await session.commit()
                await session.refresh(check)

                assert check.monitor_id == monitor.id
                assert check.run_id == run.id
                assert check.success is True
                assert check.response_time_ms == 125
                assert check.http_status_code == 200
                assert check.error_category is None
                assert check.error_message is None
                assert check.tls_expires_at == tls_expires_at
                assert check.started_at.tzinfo is not None
                assert check.completed_at.tzinfo is not None
                assert check.created_at.tzinfo is not None
        finally:
            await engine.dispose()

    asyncio.run(persist_check())


def test_monitor_check_failure_supports_null_response_and_normalized_error() -> None:
    async def persist_failure() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            monitor, _run = await create_monitor_and_run(sessions)
            started_at = datetime.now(timezone.utc)
            async with sessions() as session:
                check = MonitorCheck(
                    monitor_id=monitor.id,
                    started_at=started_at,
                    completed_at=started_at,
                    success=False,
                    response_time_ms=None,
                    http_status_code=None,
                    error_category="timeout",
                    error_message="Request timed out",
                )
                session.add(check)
                await session.commit()
                await session.refresh(check)

                assert check.run_id is None
                assert check.response_time_ms is None
                assert check.http_status_code is None
                assert check.error_category == "timeout"
                assert check.error_message == "Request timed out"
        finally:
            await engine.dispose()

    asyncio.run(persist_failure())


@pytest.mark.parametrize(
    ("response_time_ms", "http_status_code", "completion_offset"),
    [(-1, None, 0), (None, 99, 0), (None, None, -1)],
)
def test_monitor_check_constraints_reject_invalid_results(
    response_time_ms: int | None,
    http_status_code: int | None,
    completion_offset: int,
) -> None:
    async def persist_invalid_check() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            monitor, _run = await create_monitor_and_run(sessions)
            started_at = datetime.now(timezone.utc)
            async with sessions() as session:
                session.add(
                    MonitorCheck(
                        monitor_id=monitor.id,
                        started_at=started_at,
                        completed_at=started_at + timedelta(seconds=completion_offset),
                        success=False,
                        response_time_ms=response_time_ms,
                        http_status_code=http_status_code,
                    )
                )
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(persist_invalid_check())


def test_recent_monitor_checks_index_exists() -> None:
    async def inspect_indexes() -> None:
        engine = create_database_engine(database_url())
        try:
            async with engine.connect() as connection:
                indexes = await connection.run_sync(
                    lambda sync_connection: inspect(sync_connection).get_indexes(
                        "monitor_checks"
                    )
                )
        finally:
            await engine.dispose()

        recent_index = next(
            index
            for index in indexes
            if index["name"] == "ix_monitor_checks_monitor_started_at"
        )
        assert recent_index["column_names"] == ["monitor_id", "started_at"]

    asyncio.run(inspect_indexes())
