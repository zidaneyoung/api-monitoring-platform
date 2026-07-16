from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_database_session
from app.models import Monitor
from app.routes.auth import AuthenticatedSession, require_authenticated_session
from app.schemas.monitor import MonitorCreate, MonitorListResponse, MonitorResponse
from app.security.monitor_destinations import (
    DestinationResolver,
    DestinationSecurityError,
    get_destination_resolver,
    validate_monitor_destination,
)


router = APIRouter(prefix="/monitors", tags=["monitors"])


def _monitor_not_found_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "monitor_not_found",
            "message": "Monitor not found.",
        },
    )


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
    result = await session.execute(
        select(Monitor).where(
            Monitor.id == monitor_id,
            Monitor.user_id == authenticated.user.id,
        )
    )
    monitor = result.scalar_one_or_none()
    if monitor is None:
        raise _monitor_not_found_error()
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
    try:
        await validate_monitor_destination(payload.url, destination_resolver)
    except DestinationSecurityError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "unsafe_monitor_destination",
                "message": "Monitor URL must resolve to a public destination.",
            },
        ) from None

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
        next_check_at=datetime.now(timezone.utc)
        + timedelta(seconds=payload.interval_seconds),
    )
    session.add(monitor)
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "database_unavailable",
                "message": "Unable to create the monitor. Try again later.",
            },
        ) from None
    return monitor
