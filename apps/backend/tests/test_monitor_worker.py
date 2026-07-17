import asyncio
from collections.abc import Sequence
from datetime import datetime, timezone
import logging
import os
import socket
import ssl
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.celery_app import celery_app
from app.config import load_settings
from app.database import create_database_engine
from app.models import Monitor, MonitorCheck, MonitorRun, User
from app.monitoring.worker import execute_monitor_run, normalize_monitor_error


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for worker integration tests")
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


async def create_monitor_run(
    sessions: async_sessionmaker,
    *,
    email: str,
    url: str = "https://monitor.example/health",
    http_method: str = "GET",
    timeout_seconds: int = 10,
    expected_status_min: int = 200,
    expected_status_max: int = 399,
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
            expected_status_min=expected_status_min,
            expected_status_max=expected_status_max,
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
            assert checks[0].response_time_ms is not None
            assert checks[0].response_time_ms >= 0
            assert checks[0].http_status_code == 204
            assert checks[0].tls_expires_at is None
            refreshed_monitor = await session.get(Monitor, monitor.id)
            assert refreshed_monitor is not None
            assert refreshed_monitor.status == "up"
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


def test_worker_records_monotonic_response_times_for_success_and_failure() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            successful_monitor, successful_run = await create_monitor_run(
                sessions,
                email="timed-success@example.com",
            )
            failed_monitor, failed_run = await create_monitor_run(
                sessions,
                email="timed-failure@example.com",
                url="https://timed-failure.example/health",
            )

            async def handler(request: httpx.Request) -> httpx.Response:
                if request.url.host == "timed-failure.example":
                    raise httpx.ConnectError("failed", request=request)
                return httpx.Response(200, content=b"ok")

            success_clock = iter([10.0, 10.123])
            failure_clock = iter([20.0, 20.075])
            successful_result = await execute_monitor_run(
                successful_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(handler), []),
                clock=lambda: next(success_clock),
            )
            failed_result = await execute_monitor_run(
                failed_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(handler), []),
                clock=lambda: next(failure_clock),
            )
            assert successful_result.status == failed_result.status == "completed"

            async with sessions() as session:
                success_check = await session.scalar(
                    select(MonitorCheck).where(MonitorCheck.run_id == successful_run.id)
                )
                failed_check = await session.scalar(
                    select(MonitorCheck).where(MonitorCheck.run_id == failed_run.id)
                )
                refreshed_successful_monitor = await session.get(
                    Monitor, successful_monitor.id
                )
                refreshed_failed_monitor = await session.get(Monitor, failed_monitor.id)
            assert success_check is not None
            assert failed_check is not None
            assert success_check.response_time_ms == 123
            assert failed_check.response_time_ms == 75
            assert success_check.response_time_ms >= 0
            assert failed_check.response_time_ms >= 0
            assert refreshed_successful_monitor is not None
            assert refreshed_failed_monitor is not None
            assert refreshed_successful_monitor.latest_response_time_ms == 123
            assert refreshed_failed_monitor.latest_response_time_ms == 75
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_worker_records_healthy_and_unhealthy_response_statuses() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            healthy_monitor, healthy_run = await create_monitor_run(
                sessions,
                email="status-healthy@example.com",
            )
            unhealthy_monitor, unhealthy_run = await create_monitor_run(
                sessions,
                email="status-unhealthy@example.com",
                url="https://status-unhealthy.example/health",
            )

            async def handler(request: httpx.Request) -> httpx.Response:
                return httpx.Response(
                    503 if request.url.host == "status-unhealthy.example" else 204,
                    content=b"ok",
                )

            await execute_monitor_run(
                healthy_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(handler), []),
            )
            await execute_monitor_run(
                unhealthy_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(handler), []),
            )
            async with sessions() as session:
                healthy_check = await session.scalar(
                    select(MonitorCheck).where(MonitorCheck.run_id == healthy_run.id)
                )
                unhealthy_check = await session.scalar(
                    select(MonitorCheck).where(MonitorCheck.run_id == unhealthy_run.id)
                )
                refreshed_healthy = await session.get(Monitor, healthy_monitor.id)
                refreshed_unhealthy = await session.get(Monitor, unhealthy_monitor.id)
            assert healthy_check is not None and healthy_check.http_status_code == 204
            assert unhealthy_check is not None and unhealthy_check.http_status_code == 503
            assert refreshed_healthy is not None and refreshed_healthy.latest_status_code == 204
            assert refreshed_unhealthy is not None and refreshed_unhealthy.latest_status_code == 503
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("status_code", "expected_success"),
    [(200, True), (299, True), (199, False), (300, False)],
)
def test_worker_evaluates_accepted_status_range_boundaries(
    status_code: int,
    expected_success: bool,
) -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            _, run = await create_monitor_run(
                sessions,
                email=f"range-{status_code}@example.com",
                expected_status_min=200,
                expected_status_max=299,
            )

            async def handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(status_code, content=b"ok")

            await execute_monitor_run(
                run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(handler), []),
            )
            async with sessions() as session:
                check = await session.scalar(select(MonitorCheck))
            assert check is not None
            assert check.http_status_code == status_code
            assert check.success is expected_success
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("dns failure"),
        httpx.ConnectError("connection failure"),
        httpx.ConnectTimeout("timeout"),
        httpx.ReadTimeout("timeout"),
        httpx.ConnectError("tls failure"),
    ],
)
def test_worker_marks_transport_failures_unsuccessful(error: httpx.HTTPError) -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            _, run = await create_monitor_run(
                sessions,
                email=f"failure-{uuid4()}@example.com",
            )

            async def handler(request: httpx.Request) -> httpx.Response:
                raise error.__class__(str(error), request=request)

            await execute_monitor_run(
                run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(handler), []),
            )
            async with sessions() as session:
                check = await session.scalar(select(MonitorCheck))
            assert check is not None
            assert check.success is False
            assert check.http_status_code is None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("error", "category", "message"),
    [
        (httpx.ConnectError("dns"), "dns", "Monitor hostname could not be resolved."),
        (httpx.ConnectError("refused"), "connection_refused", "Monitor connection was refused."),
        (httpx.ConnectError("connect"), "connection", "Monitor connection failed."),
        (httpx.ConnectTimeout("timeout"), "connect_timeout", "Monitor connection timed out."),
        (httpx.ReadTimeout("timeout"), "request_timeout", "Monitor request timed out."),
        (httpx.ConnectError("tls"), "tls", "Monitor TLS connection failed."),
        (RuntimeError("internal"), "internal", "Monitor execution failed."),
    ],
)
def test_error_normalization_uses_safe_stable_values(
    error: Exception,
    category: str,
    message: str,
) -> None:
    if category == "dns":
        error.__cause__ = socket.gaierror("sensitive dns detail")
    elif category == "connection_refused":
        error.__cause__ = ConnectionRefusedError("sensitive connection detail")
    elif category == "tls":
        error.__cause__ = ssl.SSLError("sensitive tls detail")
    assert normalize_monitor_error(error) == (category, message)
    assert "sensitive" not in message


def test_worker_records_null_response_time_when_request_never_starts() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, run = await create_monitor_run(
                sessions,
                email="unreachable-destination@example.com",
            )

            async def unsafe_resolver(_hostname: str, _port: int) -> Sequence[str]:
                return ["127.0.0.1"]

            result = await execute_monitor_run(
                run.id,
                session_factory=sessions,
                destination_resolver=unsafe_resolver,
                client_factory=client_factory(httpx.MockTransport(lambda _: None), []),
            )
            assert result.status == "completed"
            async with sessions() as session:
                check = await session.scalar(select(MonitorCheck))
                refreshed_monitor = await session.get(Monitor, monitor.id)
            assert check is not None
            assert check.response_time_ms is None
            assert check.http_status_code is None
            assert refreshed_monitor is not None
            assert refreshed_monitor.latest_response_time_ms is None
            assert refreshed_monitor.latest_status_code is None
            assert refreshed_monitor.latest_tls_expires_at is None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_worker_records_peer_tls_expiration_for_https() -> None:
    class FakeSslObject:
        def getpeercert(self) -> dict[str, str]:
            return {"notAfter": "Jan 02 03:04:05 2030 UTC"}

    class FakeNetworkStream:
        def get_extra_info(self, name: str) -> FakeSslObject | None:
            return FakeSslObject() if name == "ssl_object" else None

    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, run = await create_monitor_run(
                sessions,
                email="tls-expiration@example.com",
            )

            async def handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(
                    204,
                    content=b"ok",
                    extensions={"network_stream": FakeNetworkStream()},
                )

            result = await execute_monitor_run(
                run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(handler), []),
            )
            assert result.status == "completed"
            expected = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
            async with sessions() as session:
                check = await session.scalar(select(MonitorCheck))
                refreshed_monitor = await session.get(Monitor, monitor.id)
            assert check is not None
            assert check.tls_expires_at == expected
            assert refreshed_monitor is not None
            assert refreshed_monitor.latest_tls_expires_at == expected
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_repeated_worker_delivery_creates_one_check_and_one_result_update() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, run = await create_monitor_run(
                sessions,
                email="idempotent@example.com",
            )

            async def handler(_request: httpx.Request) -> httpx.Response:
                await asyncio.sleep(0.02)
                return httpx.Response(204, content=b"ok")

            results = await asyncio.gather(
                execute_monitor_run(
                    run.id,
                    session_factory=sessions,
                    destination_resolver=public_resolver,
                    client_factory=client_factory(httpx.MockTransport(handler), []),
                ),
                execute_monitor_run(
                    run.id,
                    session_factory=sessions,
                    destination_resolver=public_resolver,
                    client_factory=client_factory(httpx.MockTransport(handler), []),
                ),
            )
            assert sorted(result.status for result in results) == ["completed", "skipped"]
            assert sum(result.check_created for result in results) == 1
            async with sessions() as session:
                checks = list((await session.scalars(select(MonitorCheck))).all())
                refreshed_monitor = await session.get(Monitor, monitor.id)
            assert len(checks) == 1
            assert refreshed_monitor is not None
            assert refreshed_monitor.status == "up"
            assert refreshed_monitor.consecutive_successes == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_worker_validates_each_redirect_and_records_final_response() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            _, run = await create_monitor_run(
                sessions, email="redirect@example.com", url="https://start.example/health"
            )
            resolver_calls: list[str] = []

            async def resolver(hostname: str, _port: int) -> Sequence[str]:
                resolver_calls.append(hostname)
                return ["93.184.216.34"]

            async def handler(request: httpx.Request) -> httpx.Response:
                if request.url.host == "start.example":
                    return httpx.Response(302, headers={"location": "https://final.example/ok"})
                return httpx.Response(204, content=b"ok")

            await execute_monitor_run(
                run.id, session_factory=sessions, destination_resolver=resolver,
                client_factory=client_factory(httpx.MockTransport(handler), []),
            )
            async with sessions() as session:
                check = await session.scalar(select(MonitorCheck))
            assert resolver_calls == ["start.example", "final.example"]
            assert check is not None and check.http_status_code == 204 and check.success is True
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
            assert failed_check.error_category == "connection"
            assert healthy_check.error_category is None
            assert "monitor_worker_request_failed" in caplog.messages
            assert "failed.example" not in caplog.text
            assert "connection refused" not in caplog.text
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_celery_registers_monitor_execution_task() -> None:
    assert "app.monitoring.worker.execute_monitor_run" in celery_app.tasks
