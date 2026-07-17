from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.celery_app import celery_app
from app.database import SessionFactory
from app.models import Monitor, MonitorRun
from app.monitoring.state import monitor_is_scheduler_eligible


logger = logging.getLogger(__name__)

MONITOR_EXECUTION_TASK = "app.monitoring.worker.execute_monitor_run"
RunEnqueuer = Callable[[str], None]


@dataclass(frozen=True)
class SchedulerDispatchResult:
    scheduled: int
    enqueued: int


class QueueDispatchError(RuntimeError):
    """A queue failure that leaves the run available for a later scheduler cycle."""


def enqueue_monitor_run(run_id: str) -> None:
    """Queue only a run identifier; HTTP execution belongs to the worker unit."""

    celery_app.send_task(MONITOR_EXECUTION_TASK, args=[run_id])


async def _schedule_due_monitors(
    *,
    now: datetime,
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    try:
        async with session_factory() as session:
            async with session.begin():
                due_monitors = await session.scalars(
                    select(Monitor)
                    .where(
                        Monitor.is_enabled.is_(True),
                        Monitor.status != "paused",
                        Monitor.next_check_at.is_not(None),
                        Monitor.next_check_at <= now,
                    )
                    .order_by(Monitor.next_check_at, Monitor.id)
                    .with_for_update(skip_locked=True)
                )
                monitors = list(due_monitors)
                scheduled = 0
                for monitor in monitors:
                    if not monitor_is_scheduler_eligible(monitor, now):
                        continue

                    scheduled_for = monitor.next_check_at
                    if scheduled_for is None:
                        continue
                    session.add(
                        MonitorRun(
                            monitor_id=monitor.id,
                            scheduled_for=scheduled_for,
                        )
                    )
                    monitor.next_check_at = scheduled_for + timedelta(
                        seconds=monitor.interval_seconds
                    )
                    scheduled += 1
                await session.flush()
    except SQLAlchemyError:
        logger.warning("monitor_scheduler_database_failure")
        return 0

    if scheduled:
        logger.info("monitor_scheduler_runs_created", extra={"run_count": scheduled})
    return scheduled


async def _enqueue_pending_monitor_runs(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    enqueue: RunEnqueuer,
) -> int:
    enqueued = 0
    while True:
        try:
            async with session_factory() as session:
                async with session.begin():
                    run = await session.scalar(
                        select(MonitorRun)
                        .where(
                            MonitorRun.status == "queued",
                            MonitorRun.enqueued_at.is_(None),
                        )
                        .order_by(MonitorRun.scheduled_for, MonitorRun.id)
                        .with_for_update(skip_locked=True)
                        .limit(1)
                    )
                    if run is None:
                        return enqueued

                    run_id = str(run.id)
                    try:
                        enqueue(run_id)
                    except Exception as error:
                        raise QueueDispatchError from error

                    run.enqueued_at = datetime.now(timezone.utc)
                    enqueued += 1
                    logger.info(
                        "monitor_scheduler_run_enqueued",
                        extra={"monitor_run_id": run_id},
                    )
        except QueueDispatchError:
            logger.warning("monitor_scheduler_queue_failure")
            return enqueued
        except SQLAlchemyError:
            logger.warning("monitor_scheduler_database_failure_while_enqueuing")
            return enqueued


async def dispatch_due_monitors(
    *,
    now: datetime | None = None,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    enqueue: RunEnqueuer = enqueue_monitor_run,
) -> SchedulerDispatchResult:
    """Create due runs, then queue every durable run awaiting dispatch."""

    scheduled = await _schedule_due_monitors(
        now=now or datetime.now(timezone.utc),
        session_factory=session_factory,
    )
    enqueued = await _enqueue_pending_monitor_runs(
        session_factory=session_factory,
        enqueue=enqueue,
    )
    return SchedulerDispatchResult(scheduled=scheduled, enqueued=enqueued)
