from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import logging
import socket
import ssl
import time
from urllib.parse import urljoin
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import load_settings
from app.database import SessionFactory
from app.models import (
    Incident,
    IncidentEvent,
    Monitor,
    MonitorCheck,
    MonitorRun,
    NotificationDelivery,
    User,
)
from app.monitoring.state import (
    apply_monitor_result,
    http_status_is_success,
    monitor_can_execute_request,
)
from app.notifications.dispatcher import enqueue_notification_delivery
from app.security.monitor_destinations import (
    DestinationResolver,
    DestinationSecurityError,
    get_destination_resolver,
    validate_before_connection,
    validate_redirect_destination,
)
from app.structured_logging import log_event
from app.utc import utc_now


logger = logging.getLogger(__name__)

ClientFactory = Callable[[float], httpx.AsyncClient]
Clock = Callable[[], float]
NotificationEnqueuer = Callable[[UUID], Awaitable[None]]
MAX_REDIRECTS = 5


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
    expected_status_min: int
    expected_status_max: int


@dataclass(frozen=True)
class RequestResponse:
    response_time_ms: int
    status_code: int
    tls_expires_at: datetime | None


class ResponseLimitError(RuntimeError):
    """The response body exceeded the configured safe read limit."""


class RequestAttemptError(RuntimeError):
    """A request error with its meaningful monotonic elapsed duration."""

    def __init__(self, cause: Exception, response_time_ms: int) -> None:
        super().__init__()
        self.cause = cause
        self.response_time_ms = response_time_ms


def _safe_incident_cause(check: MonitorCheck) -> tuple[str, str]:
    if check.error_category and check.error_message:
        return check.error_category, check.error_message
    return (
        "http_status",
        "Monitor response was outside the expected status range.",
    )


def _notification_deduplication_key(
    *,
    incident_id: UUID,
    event_type: str,
    destination: str,
) -> str:
    destination_digest = hashlib.sha256(
        destination.strip().casefold().encode("utf-8")
    ).hexdigest()
    return f"email:{event_type}:{incident_id}:{destination_digest}"


async def _add_incident_opening(
    session: AsyncSession,
    *,
    monitor: Monitor,
    check: MonitorCheck,
    owner_email: str,
    occurred_at: datetime,
) -> tuple[UUID, UUID] | None:
    active_incident_id = await session.scalar(
        select(Incident.id).where(
            Incident.monitor_id == monitor.id,
            Incident.status.in_(("open", "acknowledged")),
        )
    )
    if active_incident_id is not None:
        monitor.status = "down"
        return None

    cause_category, cause_message = _safe_incident_cause(check)
    incident_id = uuid4()
    delivery_id = uuid4()
    incident = Incident(
        id=incident_id,
        monitor_id=monitor.id,
        user_id=monitor.user_id,
        status="open",
        opened_at=occurred_at,
        detected_at=occurred_at,
        triggering_check=check,
        cause_category=cause_category,
        cause_message=cause_message,
    )
    session.add_all(
        [
            incident,
            IncidentEvent(
                incident=incident,
                sequence_number=1,
                event_type="opened",
                occurred_at=occurred_at,
                message=cause_message,
            ),
            NotificationDelivery(
                id=delivery_id,
                user_id=monitor.user_id,
                incident=incident,
                event_type="incident_opened",
                channel="email",
                destination=owner_email,
                status="pending",
                deduplication_key=_notification_deduplication_key(
                    incident_id=incident_id,
                    event_type="incident_opened",
                    destination=owner_email,
                ),
            ),
        ]
    )
    return delivery_id, incident_id


async def _add_incident_resolution(
    session: AsyncSession,
    *,
    monitor: Monitor,
    check: MonitorCheck,
    owner_email: str,
    occurred_at: datetime,
) -> tuple[UUID, UUID] | None:
    incident = await session.scalar(
        select(Incident)
        .where(
            Incident.monitor_id == monitor.id,
            Incident.status.in_(("open", "acknowledged")),
        )
        .with_for_update()
    )
    if incident is None:
        return None

    next_sequence = (
        await session.scalar(
            select(func.coalesce(func.max(IncidentEvent.sequence_number), 0)).where(
                IncidentEvent.incident_id == incident.id
            )
        )
    ) + 1
    incident.status = "resolved"
    incident.resolved_at = occurred_at
    incident.recovery_check = check
    monitor.status = "up"
    monitor.consecutive_failures = 0
    monitor.consecutive_successes = 0
    delivery_id = uuid4()
    session.add_all(
        [
            IncidentEvent(
                incident=incident,
                sequence_number=next_sequence,
                event_type="resolved",
                occurred_at=occurred_at,
                message="Monitor recovered after consecutive successful checks.",
            ),
            NotificationDelivery(
                id=delivery_id,
                user_id=monitor.user_id,
                incident=incident,
                event_type="incident_recovered",
                channel="email",
                destination=owner_email,
                status="pending",
                deduplication_key=_notification_deduplication_key(
                    incident_id=incident.id,
                    event_type="incident_recovered",
                    destination=owner_email,
                ),
            ),
        ]
    )
    return delivery_id, incident.id


def create_http_client(timeout_seconds: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        follow_redirects=False,
        timeout=httpx.Timeout(timeout_seconds),
    )


def normalize_monitor_error(error: Exception) -> tuple[str, str]:
    """Map provider exceptions to safe stable values without retaining details."""

    cause = error.__cause__
    if isinstance(error, DestinationSecurityError):
        return "unsafe_destination", "Monitor destination could not be reached safely."
    if isinstance(error, ResponseLimitError):
        return "response_limit", "Monitor response exceeded the safe size limit."
    if isinstance(error, httpx.TooManyRedirects):
        return "redirect", "Monitor redirect could not be completed safely."
    if isinstance(error, httpx.ConnectTimeout):
        return "connect_timeout", "Monitor connection timed out."
    if isinstance(error, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        return "request_timeout", "Monitor request timed out."
    if isinstance(cause, socket.gaierror):
        return "dns", "Monitor hostname could not be resolved."
    if isinstance(cause, ConnectionRefusedError):
        return "connection_refused", "Monitor connection was refused."
    if isinstance(cause, ssl.SSLError):
        return "tls", "Monitor TLS connection failed."
    if isinstance(error, httpx.ConnectError):
        return "connection", "Monitor connection failed."
    if isinstance(error, httpx.HTTPError):
        return "request", "Monitor request failed."
    return "internal", "Monitor execution failed."


def _certificate_expiration(response: httpx.Response) -> datetime | None:
    """Read only the peer-certificate expiry from an HTTPS transport stream."""

    stream = response.extensions.get("network_stream")
    get_extra_info = getattr(stream, "get_extra_info", None)
    if not callable(get_extra_info):
        return None
    ssl_object = get_extra_info("ssl_object")
    getpeercert = getattr(ssl_object, "getpeercert", None)
    if not callable(getpeercert):
        return None
    not_after = getpeercert().get("notAfter")
    if not isinstance(not_after, str):
        return None
    try:
        return datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)
    except ValueError:
        return None


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
                run.completed_at = utc_now()
                log_event(
                    logger,
                    logging.INFO,
                    "monitor_worker_run_expired",
                    monitor_run_id=str(run.id),
                )
                return MonitorExecutionResult("expired", False)
    except SQLAlchemyError:
        log_event(
            logger,
            logging.WARNING,
            "monitor_worker_database_failure",
            monitor_run_id=str(run_id),
        )
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
                    run.completed_at = utc_now()
                    return MonitorExecutionResult("expired", False)

                claimed_at = utc_now()
                run.status = "running"
                run.claimed_at = claimed_at
                run.started_at = claimed_at
                run.attempt_count += 1
                return None
    except SQLAlchemyError:
        log_event(
            logger,
            logging.WARNING,
            "monitor_worker_database_failure",
            monitor_run_id=str(run_id),
        )
        return MonitorExecutionResult("failed", False)


async def _load_active_request(
    run_id: UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession],
) -> MonitorRequest | MonitorExecutionResult:
    try:
        async with session_factory() as session:
            async with session.begin():
                run = await session.get(MonitorRun, run_id)
                if run is None:
                    return MonitorExecutionResult("missing", False)
                if run.status != "running":
                    return MonitorExecutionResult("skipped", False)

                monitor = await session.get(Monitor, run.monitor_id)
                if monitor is None:
                    return MonitorExecutionResult("missing", False)
                if not monitor_can_execute_request(monitor):
                    run.status = "expired"
                    run.completed_at = utc_now()
                    return MonitorExecutionResult("expired", False)
                return MonitorRequest(
                    monitor_id=monitor.id,
                    url=monitor.url,
                    http_method=monitor.http_method,
                    timeout_seconds=monitor.timeout_seconds,
                    expected_status_min=monitor.expected_status_min,
                    expected_status_max=monitor.expected_status_max,
                )
    except SQLAlchemyError:
        log_event(
            logger,
            logging.WARNING,
            "monitor_worker_database_failure",
            monitor_run_id=str(run_id),
        )
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
) -> RequestResponse:
    destination = await validate_before_connection(request.url, destination_resolver)
    async with client_factory(request.timeout_seconds) as client:
        request_started = clock()
        try:
            current_url = destination.url
            visited = {current_url}
            tls_expires_at: datetime | None = None
            for redirect_count in range(MAX_REDIRECTS + 1):
                async with client.stream(request.http_method, current_url) as response:
                    await _read_response_with_limit(
                        response,
                        max_response_bytes=max_response_bytes,
                    )
                    status_code = response.status_code
                    location = response.headers.get("location")
                    response_tls_expires_at = _certificate_expiration(response)
                if status_code not in {301, 302, 303, 307, 308} or not location:
                    tls_expires_at = response_tls_expires_at
                    break
                if redirect_count == MAX_REDIRECTS:
                    raise httpx.TooManyRedirects("redirect limit reached")
                next_url = urljoin(current_url, location)
                next_destination = await validate_redirect_destination(
                    next_url,
                    destination_resolver,
                )
                if next_destination.url in visited:
                    raise httpx.TooManyRedirects("redirect loop")
                visited.add(next_destination.url)
                current_url = next_destination.url
        except Exception as error:
            raise RequestAttemptError(
                error,
                max(0, round((clock() - request_started) * 1000)),
            ) from error
        return RequestResponse(
            response_time_ms=max(0, round((clock() - request_started) * 1000)),
            status_code=status_code,
            tls_expires_at=tls_expires_at,
        )


async def _complete_run(
    run_id: UUID,
    *,
    started_at: datetime,
    response_time_ms: int | None,
    http_status_code: int | None,
    tls_expires_at: datetime | None,
    success: bool,
    error_category: str | None,
    error_message: str | None,
    session_factory: async_sessionmaker[AsyncSession],
    notification_enqueuer: NotificationEnqueuer,
) -> MonitorExecutionResult:
    completed_at = utc_now()
    delivery_id: UUID | None = None
    incident_id: UUID | None = None
    incident_event: str | None = None
    monitor_id: UUID | None = None
    check_id = uuid4()
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
                if run.status != "running":
                    return MonitorExecutionResult("skipped", False)
                monitor = await session.scalar(
                    select(Monitor)
                    .where(Monitor.id == run.monitor_id)
                    .with_for_update()
                )
                if monitor is None:
                    return MonitorExecutionResult("missing", False)
                monitor_id = monitor.id
                existing_check = await session.scalar(
                    select(MonitorCheck.id).where(MonitorCheck.run_id == run.id)
                )
                if existing_check is not None:
                    return MonitorExecutionResult("skipped", False)

                check = MonitorCheck(
                    id=check_id,
                    monitor_id=monitor.id,
                    run_id=run.id,
                    started_at=started_at,
                    completed_at=completed_at,
                    success=success,
                    response_time_ms=response_time_ms,
                    http_status_code=http_status_code,
                    error_category=error_category,
                    error_message=error_message,
                    tls_expires_at=tls_expires_at,
                )
                session.add(check)
                monitor.last_checked_at = completed_at
                monitor.latest_response_time_ms = response_time_ms
                monitor.latest_status_code = http_status_code
                monitor.latest_error_category = error_category
                monitor.latest_tls_expires_at = tls_expires_at
                transition = apply_monitor_result(monitor, success=success)
                if transition == "incident_opened":
                    owner_email = await session.scalar(
                        select(User.email).where(User.id == monitor.user_id)
                    )
                    if owner_email is None:
                        raise SQLAlchemyError("monitor owner is missing")
                    incident_result = await _add_incident_opening(
                        session,
                        monitor=monitor,
                        check=check,
                        owner_email=owner_email,
                        occurred_at=completed_at,
                    )
                    if incident_result is not None:
                        delivery_id, incident_id = incident_result
                        incident_event = "incident_opened"
                elif transition == "incident_recovery_ready":
                    owner_email = await session.scalar(
                        select(User.email).where(User.id == monitor.user_id)
                    )
                    if owner_email is None:
                        raise SQLAlchemyError("monitor owner is missing")
                    incident_result = await _add_incident_resolution(
                        session,
                        monitor=monitor,
                        check=check,
                        owner_email=owner_email,
                        occurred_at=completed_at,
                    )
                    if incident_result is not None:
                        delivery_id, incident_id = incident_result
                        incident_event = "incident_resolved"
                run.status = "completed"
                run.completed_at = completed_at
                result = MonitorExecutionResult("completed", True)
    except SQLAlchemyError:
        log_event(
            logger,
            logging.WARNING,
            "monitor_worker_database_failure",
            monitor_run_id=str(run_id),
        )
        return MonitorExecutionResult("failed", False)

    if incident_event is not None and incident_id is not None and delivery_id is not None:
        log_event(
            logger,
            logging.INFO,
            incident_event,
            monitor_id=str(monitor_id),
            monitor_run_id=str(run_id),
            monitor_check_id=str(check_id),
            incident_id=str(incident_id),
        )
        log_event(
            logger,
            logging.INFO,
            "notification_event_created",
            incident_id=str(incident_id),
            notification_delivery_id=str(delivery_id),
        )
    if delivery_id is not None:
        try:
            await notification_enqueuer(delivery_id)
        except Exception:
            log_event(
                logger,
                logging.WARNING,
                "notification_delivery_enqueue_failed",
                notification_delivery_id=str(delivery_id),
                incident_id=str(incident_id) if incident_id is not None else None,
            )
        else:
            log_event(
                logger,
                logging.INFO,
                "notification_delivery_queued",
                notification_delivery_id=str(delivery_id),
                incident_id=str(incident_id) if incident_id is not None else None,
            )
    return result


def _worker_completion(
    run_id: UUID,
    result: MonitorExecutionResult,
    *,
    monitor_id: UUID | None = None,
) -> MonitorExecutionResult:
    log_event(
        logger,
        logging.INFO,
        "monitor_worker_completed",
        monitor_run_id=str(run_id),
        monitor_id=str(monitor_id) if monitor_id is not None else None,
        outcome=result.status,
        check_created=result.check_created,
    )
    return result


async def execute_monitor_run(
    run_id: str | UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    destination_resolver: DestinationResolver | None = None,
    client_factory: ClientFactory = create_http_client,
    max_response_bytes: int | None = None,
    clock: Clock = time.perf_counter,
    notification_enqueuer: NotificationEnqueuer | None = None,
) -> MonitorExecutionResult:
    """Execute one queued monitor run and persist a safe, bounded check record."""

    try:
        parsed_run_id = UUID(str(run_id))
    except ValueError:
        log_event(logger, logging.WARNING, "monitor_worker_invalid_run_identifier")
        return MonitorExecutionResult("missing", False)

    log_event(
        logger,
        logging.INFO,
        "monitor_worker_started",
        monitor_run_id=str(parsed_run_id),
    )

    claim_result = await _claim_run(parsed_run_id, session_factory=session_factory)
    if claim_result is not None:
        return _worker_completion(parsed_run_id, claim_result)

    request_or_result = await _load_active_request(
        parsed_run_id,
        session_factory=session_factory,
    )
    if isinstance(request_or_result, MonitorExecutionResult):
        return _worker_completion(parsed_run_id, request_or_result)

    started_at = utc_now()
    response_time_ms: int | None = None
    http_status_code: int | None = None
    tls_expires_at: datetime | None = None
    success = False
    try:
        response = await _perform_request(
            request_or_result,
            destination_resolver=destination_resolver or get_destination_resolver(),
            client_factory=client_factory,
            max_response_bytes=max_response_bytes
            if max_response_bytes is not None
            else load_settings().monitor_max_response_bytes,
            clock=clock,
        )
        response_time_ms = response.response_time_ms
        http_status_code = response.status_code
        tls_expires_at = response.tls_expires_at
        success = http_status_is_success(
            http_status_code,
            expected_status_min=request_or_result.expected_status_min,
            expected_status_max=request_or_result.expected_status_max,
        )
    except DestinationSecurityError:
        log_event(
            logger,
            logging.WARNING,
            "monitor_worker_destination_rejected",
            monitor_run_id=str(parsed_run_id),
            monitor_id=str(request_or_result.monitor_id),
            safe_error_category="unsafe_destination",
        )
        error_category, error_message = normalize_monitor_error(
            DestinationSecurityError()
        )
    except RequestAttemptError as error:
        response_time_ms = error.response_time_ms
        error_category, error_message = normalize_monitor_error(error.cause)
        log_event(
            logger,
            logging.WARNING,
            "monitor_worker_request_failed",
            monitor_run_id=str(parsed_run_id),
            monitor_id=str(request_or_result.monitor_id),
            safe_error_category=error_category,
        )
    except Exception as error:
        error_category, error_message = normalize_monitor_error(error)
        log_event(
            logger,
            logging.WARNING,
            "monitor_worker_request_failed",
            monitor_run_id=str(parsed_run_id),
            monitor_id=str(request_or_result.monitor_id),
            safe_error_category=error_category,
        )
    else:
        if success:
            error_category = None
            error_message = None
        else:
            error_category = "unexpected_status"
            error_message = "HTTP status is outside the accepted range."

    if not success:
        log_event(
            logger,
            logging.WARNING,
            "monitor_check_failed",
            monitor_run_id=str(parsed_run_id),
            monitor_id=str(request_or_result.monitor_id),
            safe_error_category=error_category,
        )

    result = await _complete_run(
        parsed_run_id,
        started_at=started_at,
        response_time_ms=response_time_ms,
        http_status_code=http_status_code,
        tls_expires_at=tls_expires_at,
        success=success,
        error_category=error_category,
        error_message=error_message,
        session_factory=session_factory,
        notification_enqueuer=(
            notification_enqueuer or enqueue_notification_delivery
        ),
    )
    return _worker_completion(
        parsed_run_id,
        result,
        monitor_id=request_or_result.monitor_id,
    )
