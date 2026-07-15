import asyncio
import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine
from app.models import Monitor, MonitorRun, User


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for database model tests")
    return value


async def create_monitor(sessions: async_sessionmaker) -> Monitor:
    async with sessions() as session:
        await session.execute(text("DELETE FROM users"))
        user = User(email="runs@example.com", password_hash="hash")
        monitor = Monitor(
            user=user,
            name="Run monitor",
            url="https://example.com",
            interval_seconds=60,
            timeout_seconds=10,
        )
        session.add(monitor)
        await session.commit()
        await session.refresh(monitor)
        return monitor


def test_monitor_run_defaults_relationship_and_utc_timestamps() -> None:
    async def persist_run() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            monitor = await create_monitor(sessions)
            scheduled_for = datetime(2026, 7, 15, 16, 0, tzinfo=timezone.utc)
            async with sessions() as session:
                run = MonitorRun(monitor_id=monitor.id, scheduled_for=scheduled_for)
                session.add(run)
                await session.commit()
                await session.refresh(run)

                assert run.monitor_id == monitor.id
                assert run.scheduled_for == scheduled_for
                assert run.status == "queued"
                assert run.attempt_count == 0
                assert run.claimed_at is None
                assert run.started_at is None
                assert run.completed_at is None
                assert run.created_at.tzinfo is not None
                assert run.updated_at.tzinfo is not None
        finally:
            await engine.dispose()

    asyncio.run(persist_run())


def test_duplicate_monitor_scheduled_time_is_rejected_safely() -> None:
    async def insert_duplicate() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            monitor = await create_monitor(sessions)
            scheduled_for = datetime(2026, 7, 15, 17, 0, tzinfo=timezone.utc)
            async with sessions() as session:
                session.add_all(
                    [
                        MonitorRun(
                            monitor_id=monitor.id, scheduled_for=scheduled_for
                        ),
                        MonitorRun(
                            monitor_id=monitor.id, scheduled_for=scheduled_for
                        ),
                    ]
                )
                with pytest.raises(IntegrityError):
                    await session.commit()
                await session.rollback()
        finally:
            await engine.dispose()

    asyncio.run(insert_duplicate())


@pytest.mark.parametrize(
    ("status", "attempt_count"),
    [("invalid", 0), ("queued", -1)],
)
def test_monitor_run_constraints_reject_invalid_state(
    status: str, attempt_count: int
) -> None:
    async def insert_invalid_run() -> None:
        engine = create_database_engine(database_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            monitor = await create_monitor(sessions)
            async with sessions() as session:
                session.add(
                    MonitorRun(
                        monitor_id=monitor.id,
                        scheduled_for=datetime.now(timezone.utc),
                        status=status,
                        attempt_count=attempt_count,
                    )
                )
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(insert_invalid_run())
