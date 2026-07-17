import os
import asyncio

from celery import Celery

from app.config import load_settings


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
    beat_schedule={
        "dispatch-due-monitors": {
            "task": "app.monitoring.scheduler.dispatch_due_monitors_task",
            "schedule": load_settings().scheduler_dispatch_interval_seconds,
        },
    },
    timezone="UTC",
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

    return asyncio.run(run_cycle())
