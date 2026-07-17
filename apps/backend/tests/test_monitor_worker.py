import asyncio
from collections.abc import Sequence
from datetime import datetime, timezone
import logging
import os
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.celery_app import celery_app
from app.database import create_database_engine
from app.models import Monitor, MonitorCheck, MonitorRun, User
from app.monitoring.worker import execute_monitor_run


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for worker integration tests")
    return value


async def create_session_factory() -> tuple[object, async_sessionmaker]:
    engine = create_database_engine(database_url())
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def reset_database(sessions: async_sessionmaker) -> None:
    async with sessions() as session:
        await session.execute(text("TRUNCATE TABLE users CASCADE"))
        await session.commit()


async def create_monitor_run(
    sessions: async_sessionmaker,
    *,
    email: str,
    url: str = "https://monitor.example/health",
    http_method: str = "GET",
    timeout_seconds: int = 10,
    enabled: bool = True,
    status: str = "unknown",
) -> tuple[Monitor, MonitorRun]:
    async with sessions() as session:
        monitor = Monitor(
            user=User(email=email, password_hash="hash"),
            name=email,
            url=url,
            http_method=http_method,
            interval_seconds=60,
            timeout_seconds=timeout_seconds,
            is_enabled=enabled,
            status=status,
            next_check_at=datetime.now(timezone.utc),
        )
        run = MonitorRun(
            monitor=monitor,
            scheduled_for=datetime.now(timezone.utc),
            enqueued_at=datetime.now(timezone.utc),
        )
        session.add(run)
        await session.commit()
        await session.refresh(monitor)
        await session.refresh(run)
        return monitor, run


async def public_resolver(_hostname: str, _port: int) -> Sequence[str]:
    return ["93.184.216.34"]


def client_factory(
    transport: httpx.AsyncBaseTransport,
    observed_timeouts: list[float],
):
    def create(timeout_seconds: float) -> httpx.AsyncClient:
        observed_timeouts.append(timeout_seconds)
        return httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
        )

    return create


@pytest.mark.parametrize("http_method", ["GET", "HEAD"])
def test_worker_processes_run_with_current_method_timeout_and_validation(
    http_method: str,
) -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, run = await create_monitor_run(
                sessions,
                email=f"{http_method.lower()}@example.com",
                http_method=http_method,
                timeout_seconds=7,
            )
            events: list[str] = []
            observed_timeouts: list[float] = []

            async def resolver(hostname: str, port: int) -> Sequence[str]:
                events.append(f"resolve:{hostname}:{port}")
                return await public_resolver(hostname, port)

            async def handler(request: httpx.Request) -> httpx.Response:
                events.append(f"request:{request.method}")
                assert request.url == httpx.URL(monitor.url)
                return httpx.Response(204, content=b"ok")

            result = await execute_monitor_run(
                run.id,
                session_factory=sessions,
                destination_resolver=resolver,
                client_factory=client_factory(
                    httpx.MockTransport(handler), observed_timeouts
                ),
            )
            assert result.status == "completed"
            assert result.check_created is True
            assert observed_timeouts == [7]
            assert events == ["resolve:monitor.example:443", f"request:{http_method}"]

            async with sessions() as session:
                stored_run = await session.get(MonitorRun, run.id)
                checks = list(
                    (await session.scalars(select(MonitorCheck))).all()
                )
            assert stored_run is not None
            assert stored_run.status == "completed"
            assert stored_run.started_at is not None
            assert stored_run.completed_at is not None
            assert len(checks) == 1
            assert checks[0].monitor_id == monitor.id
            assert checks[0].run_id == run.id
            assert checks[0].response_time_ms is None
            assert checks[0].http_status_code is None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_worker_skips_ineligible_and_missing_runs_without_checking() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            _, paused_run = await create_monitor_run(
                sessions,
                email="paused@example.com",
                enabled=False,
                status="paused",
            )
            _, disabled_run = await create_monitor_run(
                sessions,
                email="disabled@example.com",
                enabled=False,
            )
            deleted_monitor, deleted_run = await create_monitor_run(
                sessions,
                email="deleted@example.com",
            )
            async with sessions() as session:
                stored_deleted_monitor = await session.get(Monitor, deleted_monitor.id)
                assert stored_deleted_monitor is not None
                await session.delete(stored_deleted_monitor)
                await session.commit()
            missing_result = await execute_monitor_run(
                uuid4(),
                session_factory=sessions,
                destination_resolver=public_resolver,
            )
            deleted_result = await execute_monitor_run(
                deleted_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
            )
            paused_result = await execute_monitor_run(
                paused_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
            )
            disabled_result = await execute_monitor_run(
                disabled_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
            )
            assert missing_result.status == "missing"
            assert deleted_result.status == "missing"
            assert paused_result.status == "expired"
            assert disabled_result.status == "expired"

            async with sessions() as session:
                paused_stored_run = await session.get(MonitorRun, paused_run.id)
                disabled_stored_run = await session.get(MonitorRun, disabled_run.id)
                checks = list(
                    (await session.scalars(select(MonitorCheck))).all()
                )
            assert paused_stored_run is not None
            assert paused_stored_run.status == "expired"
            assert disabled_stored_run is not None
            assert disabled_stored_run.status == "expired"
            assert checks == []
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_worker_bounds_response_reading_and_records_safe_failure() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            _, run = await create_monitor_run(
                sessions,
                email="large-response@example.com",
            )

            async def handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(200, content=b"response is too large")

            result = await execute_monitor_run(
                run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(handler), []),
                max_response_bytes=4,
            )
            assert result.status == "completed"

            async with sessions() as session:
                check = await session.scalar(select(MonitorCheck))
            assert check is not None
            assert check.error_category == "response_limit"
            assert check.error_message == "Monitor response exceeded the safe size limit."
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_failed_monitor_does_not_stop_other_worker_execution(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            _, failed_run = await create_monitor_run(
                sessions,
                email="failed@example.com",
                url="https://failed.example/health",
            )
            _, healthy_run = await create_monitor_run(
                sessions,
                email="healthy@example.com",
                url="https://healthy.example/health",
            )
            caplog.set_level(logging.WARNING, logger="app.monitoring.worker")

            async def handler(request: httpx.Request) -> httpx.Response:
                if request.url.host == "failed.example":
                    raise httpx.ConnectError("connection refused", request=request)
                return httpx.Response(200, content=b"ok")

            failed_result, healthy_result = await asyncio.gather(
                execute_monitor_run(
                    failed_run.id,
                    session_factory=sessions,
                    destination_resolver=public_resolver,
                    client_factory=client_factory(httpx.MockTransport(handler), []),
                ),
                execute_monitor_run(
                    healthy_run.id,
                    session_factory=sessions,
                    destination_resolver=public_resolver,
                    client_factory=client_factory(httpx.MockTransport(handler), []),
                ),
            )
            assert failed_result.status == healthy_result.status == "completed"

            async with sessions() as session:
                checks = list(
                    (await session.scalars(select(MonitorCheck))).all()
                )
            assert len(checks) == 2
            failed_check = next(check for check in checks if check.run_id == failed_run.id)
            healthy_check = next(check for check in checks if check.run_id == healthy_run.id)
            assert failed_check.error_category == "request_failed"
            assert healthy_check.error_category is None
            assert "monitor_worker_request_failed" in caplog.messages
            assert "failed.example" not in caplog.text
            assert "connection refused" not in caplog.text
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_celery_registers_monitor_execution_task() -> None:
    assert "app.monitoring.worker.execute_monitor_run" in celery_app.tasks
