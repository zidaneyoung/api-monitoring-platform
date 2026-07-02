import os

from celery import Celery


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
    beat_schedule={},
    timezone="UTC",
)


@celery_app.task(name="app.tasks.noop")
def noop() -> str:
    return "ok"
