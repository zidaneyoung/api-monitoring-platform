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
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.celery_app import celery_app
from app.config import load_settings
from app.database import create_database_engine
from app.models import (
    Incident,
    IncidentEvent,
    Monitor,
    MonitorCheck,
    MonitorRun,
    NotificationDelivery,
    User,
)
from app.monitoring import worker
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
    failure_threshold: int = 3,
    recovery_threshold: int = 2,
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
            failure_threshold=failure_threshold,
            recovery_threshold=recovery_threshold,
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


async def create_additional_run(
    sessions: async_sessionmaker,
    monitor_id: UUID,
) -> MonitorRun:
    async with sessions() as session:
        run = MonitorRun(
            monitor_id=monitor_id,
            scheduled_for=datetime.now(timezone.utc),
            enqueued_at=datetime.now(timezone.utc),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run


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
                refreshed_monitor = await session.get(Monitor, monitor.id)
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
            assert refreshed_monitor.latest_error_category == "unsafe_destination"
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


def test_repeated_failed_delivery_increments_failure_counter_once() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, run = await create_monitor_run(
                sessions,
                email="failed-idempotent@example.com",
                failure_threshold=3,
            )

            async def handler(_request: httpx.Request) -> httpx.Response:
                await asyncio.sleep(0.02)
                return httpx.Response(500, content=b"failed")

            results = await asyncio.gather(
                *(
                    execute_monitor_run(
                        run.id,
                        session_factory=sessions,
                        destination_resolver=public_resolver,
                        client_factory=client_factory(httpx.MockTransport(handler), []),
                    )
                    for _ in range(2)
                )
            )

            assert sorted(result.status for result in results) == [
                "completed",
                "skipped",
            ]
            async with sessions() as session:
                checks = list((await session.scalars(select(MonitorCheck))).all())
                incidents = list((await session.scalars(select(Incident))).all())
                refreshed_monitor = await session.get(Monitor, monitor.id)
            assert len(checks) == 1
            assert incidents == []
            assert refreshed_monitor is not None
            assert refreshed_monitor.status == "unknown"
            assert refreshed_monitor.consecutive_failures == 1
            assert refreshed_monitor.consecutive_successes == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_failed_counter_update_rolls_back_check_and_monitor_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, run = await create_monitor_run(
                sessions,
                email="counter-rollback@example.com",
            )

            def apply_invalid_counter(current: Monitor, *, success: bool) -> None:
                assert success is False
                current.consecutive_failures = -1

            monkeypatch.setattr(worker, "apply_monitor_result", apply_invalid_counter)

            async def handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(500, content=b"failed")

            result = await execute_monitor_run(
                run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(handler), []),
            )

            assert result.status == "failed"
            assert result.check_created is False
            async with sessions() as session:
                checks = list((await session.scalars(select(MonitorCheck))).all())
                refreshed_monitor = await session.get(Monitor, monitor.id)
            assert checks == []
            assert refreshed_monitor is not None
            assert refreshed_monitor.consecutive_failures == 0
            assert refreshed_monitor.consecutive_successes == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("failure_threshold", [1, 3])
def test_failure_threshold_opens_incident_with_safe_related_events(
    failure_threshold: int,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            caplog.set_level(logging.INFO, logger="app.monitoring.worker")
            monitor, first_run = await create_monitor_run(
                sessions,
                email=f"threshold-{failure_threshold}@example.com",
                failure_threshold=failure_threshold,
            )
            provider_calls: list[str] = []

            def slow_provider(*_args: object) -> str:
                provider_calls.append("called")
                return "unexpected"

            monkeypatch.setattr(
                "app.notifications.email.send_smtp_message",
                slow_provider,
            )

            async def handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(500, content=b"unsafe body must not persist")

            runs = [first_run]
            for _ in range(1, failure_threshold):
                runs.append(await create_additional_run(sessions, monitor.id))

            enqueued_delivery_ids: list[UUID] = []

            async def record_enqueue(delivery_id: UUID) -> None:
                async with sessions() as committed_session:
                    assert (
                        await committed_session.get(NotificationDelivery, delivery_id)
                        is not None
                    )
                enqueued_delivery_ids.append(delivery_id)

            for index, run in enumerate(runs, start=1):
                result = await execute_monitor_run(
                    run.id,
                    session_factory=sessions,
                    destination_resolver=public_resolver,
                    client_factory=client_factory(httpx.MockTransport(handler), []),
                    notification_enqueuer=record_enqueue,
                )
                assert result.status == "completed"
                if index < failure_threshold:
                    async with sessions() as session:
                        assert await session.scalar(select(Incident.id)) is None

            async with sessions() as session:
                incidents = list((await session.scalars(select(Incident))).all())
                events = list((await session.scalars(select(IncidentEvent))).all())
                deliveries = list(
                    (await session.scalars(select(NotificationDelivery))).all()
                )
                checks = list(
                    (
                        await session.scalars(
                            select(MonitorCheck).order_by(MonitorCheck.completed_at)
                        )
                    ).all()
                )
                refreshed_monitor = await session.get(Monitor, monitor.id)

            assert len(incidents) == 1
            incident = incidents[0]
            assert incident.monitor_id == monitor.id
            assert incident.user_id == monitor.user_id
            assert incident.status == "open"
            assert incident.opened_at == incident.detected_at
            assert incident.opened_at.tzinfo is not None
            assert incident.triggering_check_id == checks[-1].id
            assert incident.cause_category == "unexpected_status"
            assert incident.cause_message == "HTTP status is outside the accepted range."
            assert "unsafe body" not in incident.cause_message
            assert refreshed_monitor is not None
            assert refreshed_monitor.status == "down"
            assert refreshed_monitor.consecutive_failures == failure_threshold
            assert len(events) == 1
            assert events[0].incident_id == incident.id
            assert events[0].sequence_number == 1
            assert events[0].event_type == "opened"
            assert events[0].occurred_at == incident.opened_at
            assert len(deliveries) == 1
            assert deliveries[0].incident_id == incident.id
            assert deliveries[0].user_id == monitor.user_id
            assert deliveries[0].event_type == "incident_opened"
            assert deliveries[0].channel == "email"
            assert deliveries[0].status == "pending"
            assert deliveries[0].attempt_count == 0
            assert deliveries[0].destination == f"threshold-{failure_threshold}@example.com"
            assert deliveries[0].deduplication_key == worker._notification_deduplication_key(
                incident_id=incident.id,
                event_type="incident_opened",
                destination=deliveries[0].destination,
            )
            assert enqueued_delivery_ids == [deliveries[0].id]
            assert provider_calls == []
            opened_log = next(
                record
                for record in caplog.records
                if getattr(record, "event", None) == "incident_opened"
            )
            assert opened_log.monitor_id == str(monitor.id)
            assert opened_log.monitor_run_id == str(runs[-1].id)
            assert opened_log.monitor_check_id == str(checks[-1].id)
            assert opened_log.incident_id == str(incident.id)
            notification_log = next(
                record
                for record in caplog.records
                if getattr(record, "event", None) == "notification_event_created"
            )
            assert notification_log.incident_id == str(incident.id)
            assert notification_log.notification_delivery_id == str(deliveries[0].id)
            assert {
                record.monitor_run_id
                for record in caplog.records
                if getattr(record, "event", None) == "monitor_worker_started"
            } == {str(run.id) for run in runs}
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_incident_opening_write_failure_rolls_back_complete_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, run = await create_monitor_run(
                sessions,
                email="opening-rollback@example.com",
                failure_threshold=1,
            )
            original_event = worker.IncidentEvent

            def invalid_event(**values: object) -> IncidentEvent:
                values["sequence_number"] = 0
                return original_event(**values)

            monkeypatch.setattr(worker, "IncidentEvent", invalid_event)

            async def handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(500, content=b"failed")

            enqueued_delivery_ids: list[UUID] = []

            async def record_enqueue(delivery_id: UUID) -> None:
                enqueued_delivery_ids.append(delivery_id)

            result = await execute_monitor_run(
                run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(handler), []),
                notification_enqueuer=record_enqueue,
            )

            assert result.status == "failed"
            async with sessions() as session:
                refreshed_monitor = await session.get(Monitor, monitor.id)
                assert await session.scalar(select(MonitorCheck.id)) is None
                assert await session.scalar(select(Incident.id)) is None
                assert await session.scalar(select(IncidentEvent.id)) is None
                assert await session.scalar(select(NotificationDelivery.id)) is None
            assert refreshed_monitor is not None
            assert refreshed_monitor.status == "unknown"
            assert refreshed_monitor.consecutive_failures == 0
            assert enqueued_delivery_ids == []
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_notification_enqueue_failure_does_not_roll_back_incident() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, run = await create_monitor_run(
                sessions,
                email="enqueue-failure@example.com",
                failure_threshold=1,
            )

            async def handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(500, content=b"failed")

            async def unavailable_queue(_delivery_id: UUID) -> None:
                raise ConnectionError("broker unavailable")

            result = await execute_monitor_run(
                run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(handler), []),
                notification_enqueuer=unavailable_queue,
            )

            async with sessions() as session:
                incident = await session.scalar(select(Incident))
                delivery = await session.scalar(select(NotificationDelivery))
                refreshed_monitor = await session.get(Monitor, monitor.id)
            assert result.status == "completed"
            assert incident is not None and incident.status == "open"
            assert delivery is not None and delivery.status == "pending"
            assert refreshed_monitor is not None and refreshed_monitor.status == "down"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_continued_and_duplicate_failures_reuse_active_incident() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, first_run = await create_monitor_run(
                sessions,
                email="continued-failures@example.com",
                failure_threshold=1,
            )
            second_run = await create_additional_run(sessions, monitor.id)

            async def handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(500, content=b"failed")

            for run in (first_run, second_run, second_run):
                await execute_monitor_run(
                    run.id,
                    session_factory=sessions,
                    destination_resolver=public_resolver,
                    client_factory=client_factory(httpx.MockTransport(handler), []),
                )

            async with sessions() as session:
                stale_monitor = await session.get(Monitor, monitor.id)
                assert stale_monitor is not None
                stale_monitor.status = "up"
                await session.commit()
            third_run = await create_additional_run(sessions, monitor.id)
            stale_result = await execute_monitor_run(
                third_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(handler), []),
            )
            assert stale_result.status == "completed"

            async with sessions() as session:
                incidents = list((await session.scalars(select(Incident))).all())
                events = list((await session.scalars(select(IncidentEvent))).all())
                deliveries = list(
                    (await session.scalars(select(NotificationDelivery))).all()
                )
                checks = list((await session.scalars(select(MonitorCheck))).all())
                refreshed_monitor = await session.get(Monitor, monitor.id)
            assert len(incidents) == 1
            assert incidents[0].status == "open"
            assert len(events) == 1
            assert len(deliveries) == 1
            assert len(checks) == 3
            assert refreshed_monitor is not None
            assert refreshed_monitor.status == "down"
            assert refreshed_monitor.consecutive_failures == 3
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("attempt", range(3))
def test_concurrent_threshold_workers_create_one_active_incident(attempt: int) -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, first_run = await create_monitor_run(
                sessions,
                email=f"concurrent-{attempt}@example.com",
                failure_threshold=1,
            )
            second_run = await create_additional_run(sessions, monitor.id)

            async def handler(_request: httpx.Request) -> httpx.Response:
                await asyncio.sleep(0.02)
                return httpx.Response(500, content=b"failed")

            results = await asyncio.gather(
                *(
                    execute_monitor_run(
                        run.id,
                        session_factory=sessions,
                        destination_resolver=public_resolver,
                        client_factory=client_factory(httpx.MockTransport(handler), []),
                    )
                    for run in (first_run, second_run)
                )
            )
            assert [result.status for result in results] == ["completed", "completed"]

            async with sessions() as session:
                incidents = list((await session.scalars(select(Incident))).all())
                events = list((await session.scalars(select(IncidentEvent))).all())
                deliveries = list(
                    (await session.scalars(select(NotificationDelivery))).all()
                )
                checks = list((await session.scalars(select(MonitorCheck))).all())
            assert len(incidents) == 1
            assert len(events) == 1
            assert len(deliveries) == 1
            assert len(checks) == 2
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_resolved_incident_history_survives_new_failure_sequence() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, run = await create_monitor_run(
                sessions,
                email="resolved-history@example.com",
                failure_threshold=1,
                status="up",
            )
            opened_at = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)
            async with sessions() as session:
                session.add(
                    Incident(
                        monitor_id=monitor.id,
                        user_id=monitor.user_id,
                        status="resolved",
                        opened_at=opened_at,
                        detected_at=opened_at,
                        resolved_at=opened_at,
                    )
                )
                await session.commit()

            async def handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(500, content=b"failed")

            result = await execute_monitor_run(
                run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(handler), []),
            )
            assert result.status == "completed"

            async with sessions() as session:
                incidents = list(
                    (
                        await session.scalars(
                            select(Incident).order_by(Incident.opened_at)
                        )
                    ).all()
                )
            assert [incident.status for incident in incidents] == ["resolved", "open"]
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_recovery_sequence_is_unique_interruptible_and_resolves_at_threshold() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, opening_run = await create_monitor_run(
                sessions,
                email="recovery-sequence@example.com",
                failure_threshold=1,
                recovery_threshold=2,
            )

            async def failed_handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(500, content=b"failed")

            async def success_handler(_request: httpx.Request) -> httpx.Response:
                await asyncio.sleep(0.02)
                return httpx.Response(200, content=b"ok")

            await execute_monitor_run(
                opening_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(failed_handler), []),
            )

            first_success = await create_additional_run(sessions, monitor.id)
            duplicate_results = await asyncio.gather(
                *(
                    execute_monitor_run(
                        first_success.id,
                        session_factory=sessions,
                        destination_resolver=public_resolver,
                        client_factory=client_factory(
                            httpx.MockTransport(success_handler), []
                        ),
                    )
                    for _ in range(2)
                )
            )
            assert sorted(result.status for result in duplicate_results) == [
                "completed",
                "skipped",
            ]

            interrupted = await create_additional_run(sessions, monitor.id)
            await execute_monitor_run(
                interrupted.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(failed_handler), []),
            )
            for _ in range(2):
                success_run = await create_additional_run(sessions, monitor.id)
                await execute_monitor_run(
                    success_run.id,
                    session_factory=sessions,
                    destination_resolver=public_resolver,
                    client_factory=client_factory(
                        httpx.MockTransport(success_handler), []
                    ),
                )

            async with sessions() as session:
                incident = await session.scalar(select(Incident))
                refreshed_monitor = await session.get(Monitor, monitor.id)
                checks = list((await session.scalars(select(MonitorCheck))).all())
            assert incident is not None
            assert incident.status == "resolved"
            assert incident.resolved_at is not None
            assert refreshed_monitor is not None
            assert refreshed_monitor.status == "up"
            assert refreshed_monitor.consecutive_failures == 0
            assert refreshed_monitor.consecutive_successes == 0
            assert len(checks) == 5
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_recovery_counter_write_failure_rolls_back_successful_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, opening_run = await create_monitor_run(
                sessions,
                email="recovery-rollback@example.com",
                failure_threshold=1,
                recovery_threshold=2,
            )

            async def failed_handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(500, content=b"failed")

            await execute_monitor_run(
                opening_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(failed_handler), []),
            )
            success_run = await create_additional_run(sessions, monitor.id)

            def apply_invalid_recovery(current: Monitor, *, success: bool) -> None:
                assert success is True
                current.consecutive_successes = -1

            monkeypatch.setattr(worker, "apply_monitor_result", apply_invalid_recovery)

            async def success_handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(200, content=b"ok")

            result = await execute_monitor_run(
                success_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(success_handler), []),
            )
            assert result.status == "failed"

            async with sessions() as session:
                refreshed_monitor = await session.get(Monitor, monitor.id)
                checks = list((await session.scalars(select(MonitorCheck))).all())
                incident = await session.scalar(select(Incident))
            assert refreshed_monitor is not None
            assert refreshed_monitor.status == "down"
            assert refreshed_monitor.consecutive_successes == 0
            assert len(checks) == 1
            assert incident is not None and incident.status == "open"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("recovery_threshold", [1, 3])
def test_recovery_threshold_resolves_once_and_allows_later_incident(
    recovery_threshold: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            caplog.set_level(logging.INFO, logger="app.monitoring.worker")
            monitor, opening_run = await create_monitor_run(
                sessions,
                email=f"resolve-{recovery_threshold}@example.com",
                failure_threshold=1,
                recovery_threshold=recovery_threshold,
            )

            async def failed_handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(500, content=b"failed")

            async def success_handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(200, content=b"ok")

            enqueued_delivery_ids: list[UUID] = []

            async def record_enqueue(delivery_id: UUID) -> None:
                async with sessions() as committed_session:
                    assert (
                        await committed_session.get(NotificationDelivery, delivery_id)
                        is not None
                    )
                enqueued_delivery_ids.append(delivery_id)

            await execute_monitor_run(
                opening_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(failed_handler), []),
                notification_enqueuer=record_enqueue,
            )
            async with sessions() as session:
                opened_incident = await session.scalar(select(Incident))
            assert opened_incident is not None
            original_opened_at = opened_incident.opened_at

            recovery_runs: list[MonitorRun] = []
            for index in range(1, recovery_threshold + 1):
                recovery_run = await create_additional_run(sessions, monitor.id)
                recovery_runs.append(recovery_run)
                await execute_monitor_run(
                    recovery_run.id,
                    session_factory=sessions,
                    destination_resolver=public_resolver,
                    client_factory=client_factory(
                        httpx.MockTransport(success_handler), []
                    ),
                    notification_enqueuer=record_enqueue,
                )
                if index < recovery_threshold:
                    async with sessions() as session:
                        pending_incident = await session.scalar(select(Incident))
                        pending_monitor = await session.get(Monitor, monitor.id)
                    assert pending_incident is not None
                    assert pending_incident.status == "open"
                    assert pending_incident.resolved_at is None
                    assert pending_monitor is not None
                    assert pending_monitor.status == "down"

            async with sessions() as session:
                resolved_incident = await session.scalar(select(Incident))
                resolved_monitor = await session.get(Monitor, monitor.id)
                recovery_check = await session.scalar(
                    select(MonitorCheck).where(
                        MonitorCheck.run_id == recovery_runs[-1].id
                    )
                )
                events = list(
                    (
                        await session.scalars(
                            select(IncidentEvent).order_by(
                                IncidentEvent.sequence_number
                            )
                        )
                    ).all()
                )
                deliveries = list(
                    (
                        await session.scalars(
                            select(NotificationDelivery).order_by(
                                NotificationDelivery.created_at
                            )
                        )
                    ).all()
                )
            assert resolved_incident is not None
            assert resolved_incident.status == "resolved"
            assert resolved_incident.opened_at == original_opened_at
            assert resolved_incident.resolved_at is not None
            assert resolved_incident.resolved_at.tzinfo is not None
            assert recovery_check is not None
            assert resolved_incident.recovery_check_id == recovery_check.id
            assert resolved_monitor is not None
            assert resolved_monitor.status == "up"
            assert resolved_monitor.consecutive_failures == 0
            assert resolved_monitor.consecutive_successes == 0
            assert [event.event_type for event in events] == ["opened", "resolved"]
            assert [event.sequence_number for event in events] == [1, 2]
            assert [delivery.event_type for delivery in deliveries] == [
                "incident_opened",
                "incident_recovered",
            ]
            assert all(delivery.status == "pending" for delivery in deliveries)
            assert [delivery.user_id for delivery in deliveries] == [
                monitor.user_id,
                monitor.user_id,
            ]
            assert [delivery.incident_id for delivery in deliveries] == [
                resolved_incident.id,
                resolved_incident.id,
            ]
            assert len({delivery.deduplication_key for delivery in deliveries}) == 2
            assert enqueued_delivery_ids == [delivery.id for delivery in deliveries]
            resolved_log = next(
                record
                for record in caplog.records
                if getattr(record, "event", None) == "incident_resolved"
            )
            assert resolved_log.monitor_id == str(monitor.id)
            assert resolved_log.monitor_run_id == str(recovery_runs[-1].id)
            assert resolved_log.monitor_check_id == str(recovery_check.id)
            assert resolved_log.incident_id == str(resolved_incident.id)

            fixed_resolved_at = resolved_incident.resolved_at
            additional_success = await create_additional_run(sessions, monitor.id)
            await execute_monitor_run(
                additional_success.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(success_handler), []),
                notification_enqueuer=record_enqueue,
            )
            async with sessions() as session:
                unchanged = await session.get(Incident, resolved_incident.id)
                event_count = await session.scalar(
                    select(func.count()).select_from(IncidentEvent)
                )
                delivery_count = await session.scalar(
                    select(func.count()).select_from(NotificationDelivery)
                )
            assert unchanged is not None and unchanged.resolved_at == fixed_resolved_at
            assert event_count == 2
            assert delivery_count == 2

            later_failure = await create_additional_run(sessions, monitor.id)
            await execute_monitor_run(
                later_failure.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(failed_handler), []),
            )
            async with sessions() as session:
                incidents = list(
                    (
                        await session.scalars(
                            select(Incident).order_by(Incident.opened_at)
                        )
                    ).all()
                )
            assert [incident.status for incident in incidents] == ["resolved", "open"]
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_concurrent_recovery_workers_resolve_incident_once() -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, opening_run = await create_monitor_run(
                sessions,
                email="concurrent-recovery@example.com",
                failure_threshold=1,
                recovery_threshold=1,
            )

            async def failed_handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(500, content=b"failed")

            async def success_handler(_request: httpx.Request) -> httpx.Response:
                await asyncio.sleep(0.02)
                return httpx.Response(200, content=b"ok")

            await execute_monitor_run(
                opening_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(failed_handler), []),
            )
            recovery_runs = [
                await create_additional_run(sessions, monitor.id) for _ in range(2)
            ]
            results = await asyncio.gather(
                *(
                    execute_monitor_run(
                        run.id,
                        session_factory=sessions,
                        destination_resolver=public_resolver,
                        client_factory=client_factory(
                            httpx.MockTransport(success_handler), []
                        ),
                    )
                    for run in recovery_runs
                )
            )
            assert [result.status for result in results] == ["completed", "completed"]

            async with sessions() as session:
                incident = await session.scalar(select(Incident))
                resolution_events = list(
                    (
                        await session.scalars(
                            select(IncidentEvent).where(
                                IncidentEvent.event_type == "resolved"
                            )
                        )
                    ).all()
                )
                recovery_deliveries = list(
                    (
                        await session.scalars(
                            select(NotificationDelivery).where(
                                NotificationDelivery.event_type
                                == "incident_recovered"
                            )
                        )
                    ).all()
                )
            assert incident is not None and incident.status == "resolved"
            assert len(resolution_events) == 1
            assert len(recovery_deliveries) == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_incident_resolution_write_failure_rolls_back_complete_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        engine, sessions = await create_session_factory()
        try:
            await reset_database(sessions)
            monitor, opening_run = await create_monitor_run(
                sessions,
                email="resolution-rollback@example.com",
                failure_threshold=1,
                recovery_threshold=1,
            )

            async def failed_handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(500, content=b"failed")

            await execute_monitor_run(
                opening_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(failed_handler), []),
            )
            recovery_run = await create_additional_run(sessions, monitor.id)
            original_delivery = worker.NotificationDelivery

            def invalid_delivery(**values: object) -> NotificationDelivery:
                values["destination"] = ""
                return original_delivery(**values)

            monkeypatch.setattr(worker, "NotificationDelivery", invalid_delivery)

            async def success_handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(200, content=b"ok")

            result = await execute_monitor_run(
                recovery_run.id,
                session_factory=sessions,
                destination_resolver=public_resolver,
                client_factory=client_factory(httpx.MockTransport(success_handler), []),
            )
            assert result.status == "failed"

            async with sessions() as session:
                incident = await session.scalar(select(Incident))
                refreshed_monitor = await session.get(Monitor, monitor.id)
                checks = list((await session.scalars(select(MonitorCheck))).all())
                events = list((await session.scalars(select(IncidentEvent))).all())
                deliveries = list(
                    (await session.scalars(select(NotificationDelivery))).all()
                )
            assert incident is not None
            assert incident.status == "open"
            assert incident.resolved_at is None
            assert incident.recovery_check_id is None
            assert refreshed_monitor is not None
            assert refreshed_monitor.status == "down"
            assert len(checks) == 1
            assert [event.event_type for event in events] == ["opened"]
            assert [delivery.event_type for delivery in deliveries] == [
                "incident_opened"
            ]
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
