import asyncio
from datetime import datetime, timedelta, timezone
import logging
import os
from uuid import UUID

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.celery_app import celery_app
from app.config import load_settings
from app.database import create_database_engine
from app.models import Monitor, MonitorRun, User
from app.monitoring.scheduler import dispatch_due_monitors


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for scheduler integration tests")
    if make_url(value).render_as_string(hide_password=True) == make_url(
        load_settings().database_url
    ).render_as_string(hide_password=True):
        pytest.fail("TEST_DATABASE_URL must not target the application database")
    return value


async def create_session_factory() -> tuple[object, async_sessionmaker]:
    engine = create_database_engine(database_url())
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def reset_database(sessions: async_sessionmaker) -> None:
    async with sessions() as session:
        await session.execute(text("TRUNCATE TABLE users CASCADE"))
        await session.commit()


async def create_monitor(
    sessions: async_sessionmaker,
    *,
    email: str,
    now: datetime,
    enabled: bool = True,
    status: str = "unknown",
    next_check_at: datetime | None = None,
) -> Monitor:
    async with sessions() as session:
        monitor = Monitor(
            user=User(email=email, password_hash="hash"),
            name=email,
            url="https://example.com",
            interval_seconds=60,
            timeout_seconds=10,
            is_enabled=enabled,
            status=status,
            next_check_at=next_check_at if next_check_at is not None else now,
        )
        session.add(monitor)
        await session.commit()
        await session.refresh(monitor)
        return monitor


def test_scheduler_selects_due_monitors_and_queues_run_identifiers() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
            first_due = await create_monitor(
                sessions,
                email="first-due@example.com",
                now=now,
                next_check_at=now - timedelta(seconds=30),
            )
            second_due = await create_monitor(
                sessions,
                email="second-due@example.com",
                now=now,
            )
            await create_monitor(
                sessions,
                email="future@example.com",
                now=now,
                next_check_at=now + timedelta(seconds=1),
            )
            await create_monitor(
                sessions,
                email="paused@example.com",
                now=now,
                enabled=False,
                status="paused",
            )
            deleted = await create_monitor(
                sessions,
                email="deleted@example.com",
                now=now,
            )
            async with sessions() as session:
                await session.delete(deleted)
                await session.commit()

            queued: list[str] = []
            result = await dispatch_due_monitors(
                now=now,
                session_factory=sessions,
                enqueue=queued.append,
            )

            assert result.scheduled == 2
            assert result.enqueued == 2
            async with sessions() as session:
                runs = list(
                    (
                        await session.scalars(
                            select(MonitorRun).order_by(MonitorRun.scheduled_for)
                        )
                    ).all()
                )
                monitors = {
                    monitor.id: monitor
                    for monitor in (
                        await session.scalars(select(Monitor))
                    ).all()
                }

            assert {run.monitor_id for run in runs} == {first_due.id, second_due.id}
            assert {str(run.id) for run in runs} == set(queued)
            assert all(run.enqueued_at is not None for run in runs)
            assert monitors[first_due.id].next_check_at == now + timedelta(seconds=30)
            assert monitors[second_due.id].next_check_at == now + timedelta(seconds=60)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_queue_failure_leaves_run_for_a_later_scheduler_cycle() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            now = datetime(2026, 7, 17, 13, 0, tzinfo=timezone.utc)
            monitor = await create_monitor(
                sessions,
                email="retry@example.com",
                now=now,
            )

            def unavailable_queue(_: str) -> None:
                raise RuntimeError("broker unavailable")

            first_result = await dispatch_due_monitors(
                now=now,
                session_factory=sessions,
                enqueue=unavailable_queue,
            )
            assert first_result.scheduled == 1
            assert first_result.enqueued == 0

            async with sessions() as session:
                run = await session.scalar(select(MonitorRun))
                refreshed_monitor = await session.get(Monitor, monitor.id)
                assert run is not None
                assert run.enqueued_at is None
                assert refreshed_monitor is not None
                assert refreshed_monitor.next_check_at == now + timedelta(seconds=60)

            queued: list[str] = []
            second_result = await dispatch_due_monitors(
                now=now,
                session_factory=sessions,
                enqueue=queued.append,
            )
            assert second_result.scheduled == 0
            assert second_result.enqueued == 1
            assert queued == [str(run.id)]
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_database_failure_does_not_advance_a_due_monitor() -> None:
    class UnavailableSession:
        async def __aenter__(self) -> None:
            raise OperationalError("SELECT 1", {}, OSError("database unavailable"))

        async def __aexit__(self, *_: object) -> None:
            return None

    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            now = datetime(2026, 7, 17, 14, 0, tzinfo=timezone.utc)
            monitor = await create_monitor(
                sessions,
                email="database-retry@example.com",
                now=now,
            )
            result = await dispatch_due_monitors(
                now=now,
                session_factory=lambda: UnavailableSession(),  # type: ignore[arg-type]
                enqueue=lambda _: None,
            )
            assert result.scheduled == 0
            assert result.enqueued == 0

            async with sessions() as session:
                refreshed_monitor = await session.get(Monitor, monitor.id)
                runs = list((await session.scalars(select(MonitorRun))).all())
            assert refreshed_monitor is not None
            assert refreshed_monitor.next_check_at == now
            assert runs == []
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_scheduler_recovers_from_a_preexisting_unique_run_conflict(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            caplog.set_level(logging.WARNING, logger="app.monitoring.scheduler")
            now = datetime(2026, 7, 17, 15, 0, tzinfo=timezone.utc)
            monitor = await create_monitor(
                sessions,
                email="unique-conflict@example.com",
                now=now,
            )
            async with sessions() as session:
                existing_run = MonitorRun(
                    monitor_id=monitor.id,
                    scheduled_for=now,
                )
                session.add(existing_run)
                await session.commit()
                await session.refresh(existing_run)

            queued: list[str] = []
            result = await dispatch_due_monitors(
                now=now,
                session_factory=sessions,
                enqueue=queued.append,
            )
            assert result.scheduled == 0
            assert result.enqueued == 1
            assert queued == [str(existing_run.id)]

            async with sessions() as session:
                runs = list((await session.scalars(select(MonitorRun))).all())
                refreshed_monitor = await session.get(Monitor, monitor.id)
            assert len(runs) == 1
            assert runs[0].id == existing_run.id
            assert runs[0].enqueued_at is not None
            assert refreshed_monitor is not None
            assert refreshed_monitor.next_check_at == now + timedelta(seconds=60)
            assert "monitor_scheduler_duplicate_run" in caplog.messages
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_concurrent_scheduler_cycles_create_and_queue_one_run() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            for attempt in range(3):
                await reset_database(sessions)
                now = datetime(2026, 7, 17, 16, attempt, tzinfo=timezone.utc)
                monitor = await create_monitor(
                    sessions,
                    email=f"concurrent-{attempt}@example.com",
                    now=now,
                )
                queued: list[str] = []

                first, second = await asyncio.gather(
                    dispatch_due_monitors(
                        now=now,
                        session_factory=sessions,
                        enqueue=queued.append,
                    ),
                    dispatch_due_monitors(
                        now=now,
                        session_factory=sessions,
                        enqueue=queued.append,
                    ),
                )

                assert first.scheduled + second.scheduled == 1
                assert first.enqueued + second.enqueued == 1
                assert len(queued) == 1
                async with sessions() as session:
                    runs = list((await session.scalars(select(MonitorRun))).all())
                    refreshed_monitor = await session.get(Monitor, monitor.id)
                assert len(runs) == 1
                assert str(runs[0].id) == queued[0]
                assert runs[0].scheduled_for == now
                assert runs[0].enqueued_at is not None
                assert refreshed_monitor is not None
                assert refreshed_monitor.next_check_at == now + timedelta(seconds=60)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_celery_beat_registers_the_due_monitor_dispatcher() -> None:
    entry = celery_app.conf.beat_schedule["dispatch-due-monitors"]
    assert entry["task"] == "app.monitoring.scheduler.dispatch_due_monitors_task"
    assert entry["schedule"] == 30
