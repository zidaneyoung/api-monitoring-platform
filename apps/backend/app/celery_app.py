import asyncio
import logging
import os

from celery import Celery
from celery.signals import after_setup_logger, after_setup_task_logger

from app.config import load_settings
from app.notifications.constants import EMAIL_DELIVERY_TASK
from app.structured_logging import (
    bind_log_context,
    configure_structured_logging,
    new_correlation_id,
)


configure_structured_logging()


@after_setup_logger.connect
@after_setup_task_logger.connect
def configure_celery_logging(**_: object) -> None:
    configure_structured_logging()


def _redis_url() -> str:
    return os.getenv(
        "CELERY_BROKER_URL",
        os.getenv("REDIS_URL", "redis://redis:6379/0"),
    )


celery_app = Celery(
    "api_monitoring_platform",
    broker=_redis_url(),
    backend=os.getenv("CELERY_RESULT_BACKEND", _redis_url()),
)

celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
    beat_schedule={
        "dispatch-due-monitors": {
            "task": "app.monitoring.scheduler.dispatch_due_monitors_task",
            "schedule": load_settings().scheduler_dispatch_interval_seconds,
        },
    },
    timezone="UTC",
    task_routes={EMAIL_DELIVERY_TASK: {"queue": "email"}},
)


@celery_app.task(name="app.tasks.noop")
def noop() -> str:
    return "ok"


@celery_app.task(name="app.monitoring.scheduler.dispatch_due_monitors_task")
def dispatch_due_monitors_task() -> dict[str, int]:
    """Run one scheduler cycle without executing any monitor request."""

    from app.database import dispose_database_engine
    from app.monitoring.scheduler import dispatch_due_monitors

    async def run_cycle() -> dict[str, int]:
        try:
            result = await dispatch_due_monitors()
            return {"scheduled": result.scheduled, "enqueued": result.enqueued}
        finally:
            await dispose_database_engine()

    with bind_log_context(correlation_id=new_correlation_id()):
        return asyncio.run(run_cycle())


@celery_app.task(name="app.monitoring.worker.execute_monitor_run")
def execute_monitor_run_task(run_id: str) -> dict[str, str | bool]:
    """Execute one queued monitor run; request details stay in the worker module."""

    from app.database import dispose_database_engine
    from app.monitoring.worker import execute_monitor_run

    async def run_task() -> dict[str, str | bool]:
        try:
            result = await execute_monitor_run(run_id)
            return {"status": result.status, "check_created": result.check_created}
        finally:
            await dispose_database_engine()

    with bind_log_context(
        correlation_id=run_id,
        monitor_run_id=run_id,
    ):
        return asyncio.run(run_task())


@celery_app.task(
    name=EMAIL_DELIVERY_TASK,
    acks_late=True,
    reject_on_worker_lost=True,
)
def deliver_notification_task(delivery_id: str) -> str:
    """Deliver one durable email record on the dedicated email queue."""

    from app.database import dispose_database_engine
    from app.notifications.email import deliver_notification

    async def run_task() -> str:
        try:
            return await deliver_notification(delivery_id)
        finally:
            await dispose_database_engine()

    with bind_log_context(
        correlation_id=delivery_id,
        notification_delivery_id=delivery_id,
    ):
        return asyncio.run(run_task())
