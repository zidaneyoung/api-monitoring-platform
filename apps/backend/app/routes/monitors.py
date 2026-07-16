from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_database_session
from app.models import Monitor
from app.routes.auth import AuthenticatedSession, require_authenticated_session
from app.schemas.monitor import MonitorCreate, MonitorResponse


router = APIRouter(prefix="/monitors", tags=["monitors"])


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
) -> Monitor:
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
