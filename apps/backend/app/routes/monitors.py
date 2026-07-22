from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_database_session
from app.models import Monitor, MonitorCheck
from app.routes.auth import AuthenticatedSession, require_authenticated_session
from app.schemas.monitor import (
    MonitorCreate,
    MonitorCheckListResponse,
    MonitorListResponse,
    MonitorResponse,
    MonitorResponseTimePoint,
    MonitorResponseTimeSeriesResponse,
    MonitorSummaryResponse,
    MonitorUpdate,
)
from app.security.monitor_destinations import (
    DestinationResolver,
    DestinationSecurityError,
    get_destination_resolver,
    validate_monitor_destination,
)
from app.utc import utc_now


router = APIRouter(prefix="/monitors", tags=["monitors"])
_CONFIGURATION_FIELDS = (
    "name",
    "url",
    "http_method",
    "interval_seconds",
    "timeout_seconds",
    "expected_status_min",
    "expected_status_max",
    "failure_threshold",
    "recovery_threshold",
)


def _monitor_not_found_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "monitor_not_found",
            "message": "Monitor not found.",
        },
    )


def _database_unavailable_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "database_unavailable",
            "message": message,
        },
    )


def _unsafe_destination_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "unsafe_monitor_destination",
            "message": "Monitor URL must resolve to a public destination.",
        },
    )


async def _owned_monitor(
    session: AsyncSession,
    monitor_id: UUID,
    owner_id: UUID,
) -> Monitor:
    result = await session.execute(
        select(Monitor).where(
            Monitor.id == monitor_id,
            Monitor.user_id == owner_id,
        )
    )
    monitor = result.scalar_one_or_none()
    if monitor is None:
        raise _monitor_not_found_error()
    return monitor


async def _validate_destination(
    url: str,
    destination_resolver: DestinationResolver,
) -> None:
    try:
        await validate_monitor_destination(url, destination_resolver)
    except DestinationSecurityError:
        raise _unsafe_destination_error() from None


@router.get("", response_model=MonitorListResponse)
async def list_monitors(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    authenticated: AuthenticatedSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_database_session),
) -> MonitorListResponse:
    owner_filter = Monitor.user_id == authenticated.user.id
    total = await session.scalar(
        select(func.count()).select_from(Monitor).where(owner_filter)
    )
    result = await session.execute(
        select(Monitor)
        .where(owner_filter)
        .order_by(Monitor.created_at.desc(), Monitor.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return MonitorListResponse.from_items(
        items=list(result.scalars()),
        page=page,
        page_size=page_size,
        total=total or 0,
    )


@router.get(
    "/summary",
    response_model=MonitorSummaryResponse,
    summary="Summarize owned persisted monitors by state",
)
async def summarize_monitors(
    authenticated: AuthenticatedSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_database_session),
) -> MonitorSummaryResponse:
    """Total is the sum of unknown, up, down, and paused persisted monitors."""

    result = await session.execute(
        select(Monitor.status, func.count())
        .where(Monitor.user_id == authenticated.user.id)
        .group_by(Monitor.status)
    )
    counts = {"unknown": 0, "up": 0, "down": 0, "paused": 0}
    for monitor_status, count in result:
        counts[monitor_status] = count
    return MonitorSummaryResponse(total=sum(counts.values()), **counts)


@router.get(
    "/{monitor_id}/checks",
    response_model=MonitorCheckListResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_404_NOT_FOUND: {"description": "Monitor not found."},
    },
)
async def list_monitor_checks(
    monitor_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    authenticated: AuthenticatedSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_database_session),
) -> MonitorCheckListResponse:
    await _owned_monitor(session, monitor_id, authenticated.user.id)
    check_filter = MonitorCheck.monitor_id == monitor_id
    total = await session.scalar(
        select(func.count()).select_from(MonitorCheck).where(check_filter)
    )
    result = await session.execute(
        select(MonitorCheck)
        .where(check_filter)
        .order_by(MonitorCheck.completed_at.desc(), MonitorCheck.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return MonitorCheckListResponse.from_items(
        items=list(result.scalars()),
        page=page,
        page_size=page_size,
        total=total or 0,
    )


@router.get(
    "/{monitor_id}/response-times",
    response_model=MonitorResponseTimeSeriesResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_404_NOT_FOUND: {"description": "Monitor not found."},
    },
)
async def get_monitor_response_times(
    monitor_id: UUID,
    selected_range: Literal["24h"] = Query(default="24h", alias="range"),
    authenticated: AuthenticatedSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_database_session),
) -> MonitorResponseTimeSeriesResponse:
    await _owned_monitor(session, monitor_id, authenticated.user.id)
    ended_at = utc_now()
    started_at = ended_at - timedelta(hours=24)
    result = await session.execute(
        select(MonitorCheck)
        .where(
            MonitorCheck.monitor_id == monitor_id,
            MonitorCheck.completed_at >= started_at,
            MonitorCheck.completed_at <= ended_at,
        )
        .order_by(MonitorCheck.completed_at.asc(), MonitorCheck.id.asc())
    )
    return MonitorResponseTimeSeriesResponse(
        range=selected_range,
        started_at=started_at,
        ended_at=ended_at,
        points=[
            MonitorResponseTimePoint.model_validate(check)
            for check in result.scalars()
        ],
    )


@router.get(
    "/{monitor_id}",
    response_model=MonitorResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_404_NOT_FOUND: {"description": "Monitor not found."},
    },
)
async def get_monitor(
    monitor_id: UUID,
    authenticated: AuthenticatedSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_database_session),
) -> Monitor:
    return await _owned_monitor(session, monitor_id, authenticated.user.id)


@router.post(
    "/{monitor_id}/pause",
    response_model=MonitorResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_404_NOT_FOUND: {"description": "Monitor not found."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Monitor storage unavailable."
        },
    },
)
async def pause_monitor(
    monitor_id: UUID,
    authenticated: AuthenticatedSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_database_session),
) -> Monitor:
    monitor = await _owned_monitor(session, monitor_id, authenticated.user.id)
    if (
        monitor.status == "paused"
        and not monitor.is_enabled
        and monitor.next_check_at is None
    ):
        return monitor

    monitor.status = "paused"
    monitor.is_enabled = False
    monitor.next_check_at = None
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise _database_unavailable_error(
            "Unable to pause the monitor. Try again later."
        ) from None
    return monitor


@router.post(
    "/{monitor_id}/resume",
    response_model=MonitorResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_404_NOT_FOUND: {"description": "Monitor not found."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Monitor storage unavailable."
        },
    },
)
async def resume_monitor(
    monitor_id: UUID,
    authenticated: AuthenticatedSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_database_session),
) -> Monitor:
    monitor = await _owned_monitor(session, monitor_id, authenticated.user.id)
    now = utc_now()
    if (
        monitor.status != "paused"
        and monitor.is_enabled
        and monitor.next_check_at is not None
        and monitor.next_check_at > now
    ):
        return monitor

    if monitor.status == "paused":
        monitor.status = "unknown"
    monitor.is_enabled = True
    monitor.next_check_at = now + timedelta(seconds=monitor.interval_seconds)
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise _database_unavailable_error(
            "Unable to resume the monitor. Try again later."
        ) from None
    return monitor


@router.delete(
    "/{monitor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_404_NOT_FOUND: {"description": "Monitor not found."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Monitor storage unavailable."
        },
    },
)
async def delete_monitor(
    monitor_id: UUID,
    authenticated: AuthenticatedSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_database_session),
) -> Response:
    monitor = await _owned_monitor(session, monitor_id, authenticated.user.id)
    await session.delete(monitor)
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise _database_unavailable_error(
            "Unable to delete the monitor. Try again later."
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{monitor_id}",
    response_model=MonitorResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_404_NOT_FOUND: {"description": "Monitor not found."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Monitor storage unavailable."
        },
    },
)
async def update_monitor(
    monitor_id: UUID,
    payload: MonitorUpdate,
    authenticated: AuthenticatedSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_database_session),
    destination_resolver: DestinationResolver = Depends(get_destination_resolver),
) -> Monitor:
    monitor = await _owned_monitor(session, monitor_id, authenticated.user.id)
    await _validate_destination(payload.url, destination_resolver)

    interval_changed = monitor.interval_seconds != payload.interval_seconds
    for field in _CONFIGURATION_FIELDS:
        setattr(monitor, field, getattr(payload, field))
    if interval_changed and monitor.is_enabled:
        monitor.next_check_at = utc_now() + timedelta(
            seconds=payload.interval_seconds
        )

    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise _database_unavailable_error(
            "Unable to update the monitor. Try again later."
        ) from None
    return monitor


@router.post(
    "",
    response_model=MonitorResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Monitor storage unavailable."
        },
    },
)
async def create_monitor(
    payload: MonitorCreate,
    authenticated: AuthenticatedSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_database_session),
    destination_resolver: DestinationResolver = Depends(get_destination_resolver),
) -> Monitor:
    await _validate_destination(payload.url, destination_resolver)

    monitor = Monitor(
        id=uuid4(),
        user_id=authenticated.user.id,
        name=payload.name,
        url=payload.url,
        http_method=payload.http_method,
        interval_seconds=payload.interval_seconds,
        timeout_seconds=payload.timeout_seconds,
        expected_status_min=payload.expected_status_min,
        expected_status_max=payload.expected_status_max,
        failure_threshold=payload.failure_threshold,
        recovery_threshold=payload.recovery_threshold,
        status="unknown",
        is_enabled=True,
        consecutive_failures=0,
        consecutive_successes=0,
        next_check_at=utc_now()
        + timedelta(seconds=payload.interval_seconds),
    )
    session.add(monitor)
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise _database_unavailable_error(
            "Unable to create the monitor. Try again later."
        ) from None
    return monitor
