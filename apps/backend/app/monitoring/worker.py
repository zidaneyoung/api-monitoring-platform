from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import load_settings
from app.database import SessionFactory
from app.models import Monitor, MonitorCheck, MonitorRun
from app.monitoring.state import monitor_can_execute_request
from app.security.monitor_destinations import (
    DestinationResolver,
    DestinationSecurityError,
    get_destination_resolver,
    validate_before_connection,
)


logger = logging.getLogger(__name__)

ClientFactory = Callable[[float], httpx.AsyncClient]
Clock = Callable[[], float]


@dataclass(frozen=True)
class MonitorExecutionResult:
    status: str
    check_created: bool


@dataclass(frozen=True)
class MonitorRequest:
    monitor_id: UUID
    url: str
    http_method: str
    timeout_seconds: int


class ResponseLimitError(RuntimeError):
    """The response body exceeded the configured safe read limit."""


class RequestAttemptError(RuntimeError):
    """A request error with its meaningful monotonic elapsed duration."""

    def __init__(self, cause: Exception, response_time_ms: int) -> None:
        super().__init__()
        self.cause = cause
        self.response_time_ms = response_time_ms


def create_http_client(timeout_seconds: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        follow_redirects=False,
        timeout=httpx.Timeout(timeout_seconds),
    )


async def _expire_run(
    run_id: UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession],
) -> MonitorExecutionResult:
    try:
        async with session_factory() as session:
            async with session.begin():
                run = await session.scalar(
                    select(MonitorRun)
                    .where(MonitorRun.id == run_id)
                    .with_for_update()
                )
                if run is None:
                    return MonitorExecutionResult("missing", False)
                if run.status in {"completed", "failed", "expired"}:
                    return MonitorExecutionResult("skipped", False)
                run.status = "expired"
                run.completed_at = datetime.now(timezone.utc)
                logger.info(
                    "monitor_worker_run_expired",
                    extra={"monitor_run_id": str(run.id)},
                )
                return MonitorExecutionResult("expired", False)
    except SQLAlchemyError:
        logger.warning("monitor_worker_database_failure")
        return MonitorExecutionResult("failed", False)


async def _claim_run(
    run_id: UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession],
) -> MonitorExecutionResult | None:
    try:
        async with session_factory() as session:
            async with session.begin():
                run = await session.scalar(
                    select(MonitorRun)
                    .where(MonitorRun.id == run_id)
                    .with_for_update()
                )
                if run is None:
                    return MonitorExecutionResult("missing", False)
                if run.status != "queued":
                    return MonitorExecutionResult("skipped", False)

                monitor = await session.get(Monitor, run.monitor_id)
                if not monitor_can_execute_request(monitor):
                    run.status = "expired"
                    run.completed_at = datetime.now(timezone.utc)
                    return MonitorExecutionResult("expired", False)

                claimed_at = datetime.now(timezone.utc)
                run.status = "running"
                run.claimed_at = claimed_at
                run.started_at = claimed_at
                run.attempt_count += 1
                return None
    except SQLAlchemyError:
        logger.warning("monitor_worker_database_failure")
        return MonitorExecutionResult("failed", False)


async def _load_active_request(
    run_id: UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession],
) -> MonitorRequest | MonitorExecutionResult:
    try:
        async with session_factory() as session:
            run = await session.get(MonitorRun, run_id)
            if run is None:
                return MonitorExecutionResult("missing", False)
            if run.status != "running":
                return MonitorExecutionResult("skipped", False)

            monitor = await session.get(Monitor, run.monitor_id)
            if not monitor_can_execute_request(monitor):
                return await _expire_run(run_id, session_factory=session_factory)
            if monitor is None:
                return MonitorExecutionResult("missing", False)
            return MonitorRequest(
                monitor_id=monitor.id,
                url=monitor.url,
                http_method=monitor.http_method,
                timeout_seconds=monitor.timeout_seconds,
            )
    except SQLAlchemyError:
        logger.warning("monitor_worker_database_failure")
        return MonitorExecutionResult("failed", False)


async def _read_response_with_limit(
    response: httpx.Response,
    *,
    max_response_bytes: int,
) -> None:
    received = 0
    async for chunk in response.aiter_bytes():
        received += len(chunk)
        if received > max_response_bytes:
            raise ResponseLimitError


async def _perform_request(
    request: MonitorRequest,
    *,
    destination_resolver: DestinationResolver,
    client_factory: ClientFactory,
    max_response_bytes: int,
    clock: Clock,
) -> int:
    destination = await validate_before_connection(request.url, destination_resolver)
    async with client_factory(request.timeout_seconds) as client:
        request_started = clock()
        try:
            async with client.stream(request.http_method, destination.url) as response:
                await _read_response_with_limit(
                    response,
                    max_response_bytes=max_response_bytes,
                )
        except Exception as error:
            raise RequestAttemptError(
                error,
                max(0, round((clock() - request_started) * 1000)),
            ) from error
        return max(0, round((clock() - request_started) * 1000))


async def _complete_run(
    run_id: UUID,
    *,
    started_at: datetime,
    response_time_ms: int | None,
    error_category: str | None,
    error_message: str | None,
    session_factory: async_sessionmaker[AsyncSession],
) -> MonitorExecutionResult:
    completed_at = datetime.now(timezone.utc)
    try:
        async with session_factory() as session:
            async with session.begin():
                run = await session.scalar(
                    select(MonitorRun)
                    .where(MonitorRun.id == run_id)
                    .with_for_update()
                )
                if run is None:
                    return MonitorExecutionResult("missing", False)
                monitor = await session.get(Monitor, run.monitor_id)
                if monitor is None:
                    return MonitorExecutionResult("missing", False)

                session.add(
                    MonitorCheck(
                        monitor_id=monitor.id,
                        run_id=run.id,
                        started_at=started_at,
                        completed_at=completed_at,
                        success=False,
                        response_time_ms=response_time_ms,
                        error_category=error_category,
                        error_message=error_message,
                    )
                )
                monitor.last_checked_at = completed_at
                monitor.latest_response_time_ms = response_time_ms
                run.status = "completed"
                run.completed_at = completed_at
                return MonitorExecutionResult("completed", True)
    except SQLAlchemyError:
        logger.warning("monitor_worker_database_failure")
        return MonitorExecutionResult("failed", False)


async def execute_monitor_run(
    run_id: str | UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    destination_resolver: DestinationResolver | None = None,
    client_factory: ClientFactory = create_http_client,
    max_response_bytes: int | None = None,
    clock: Clock = time.perf_counter,
) -> MonitorExecutionResult:
    """Execute one queued monitor run and persist a safe, bounded check record."""

    try:
        parsed_run_id = UUID(str(run_id))
    except ValueError:
        logger.warning("monitor_worker_invalid_run_identifier")
        return MonitorExecutionResult("missing", False)

    claim_result = await _claim_run(parsed_run_id, session_factory=session_factory)
    if claim_result is not None:
        return claim_result

    request_or_result = await _load_active_request(
        parsed_run_id,
        session_factory=session_factory,
    )
    if isinstance(request_or_result, MonitorExecutionResult):
        return request_or_result

    started_at = datetime.now(timezone.utc)
    response_time_ms: int | None = None
    try:
        response_time_ms = await _perform_request(
            request_or_result,
            destination_resolver=destination_resolver or get_destination_resolver(),
            client_factory=client_factory,
            max_response_bytes=max_response_bytes
            if max_response_bytes is not None
            else load_settings().monitor_max_response_bytes,
            clock=clock,
        )
    except DestinationSecurityError:
        logger.warning("monitor_worker_destination_rejected")
        error_category = "unsafe_destination"
        error_message = "Monitor destination could not be reached safely."
    except RequestAttemptError as error:
        response_time_ms = error.response_time_ms
        if isinstance(error.cause, ResponseLimitError):
            logger.warning("monitor_worker_response_limit_exceeded")
            error_category = "response_limit"
            error_message = "Monitor response exceeded the safe size limit."
        elif isinstance(error.cause, httpx.HTTPError):
            logger.warning("monitor_worker_request_failed")
            error_category = "request_failed"
            error_message = "Monitor request failed."
        else:
            logger.warning("monitor_worker_internal_failure")
            error_category = "internal_error"
            error_message = "Monitor execution failed."
    except httpx.HTTPError:
        logger.warning("monitor_worker_request_failed")
        error_category = "request_failed"
        error_message = "Monitor request failed."
    except Exception:
        logger.warning("monitor_worker_internal_failure")
        error_category = "internal_error"
        error_message = "Monitor execution failed."
    else:
        error_category = None
        error_message = None

    return await _complete_run(
        parsed_run_id,
        started_at=started_at,
        response_time_ms=response_time_ms,
        error_category=error_category,
        error_message=error_message,
        session_factory=session_factory,
    )
