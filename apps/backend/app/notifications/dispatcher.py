import logging
from uuid import UUID

from app.celery_app import celery_app
from app.notifications.constants import EMAIL_DELIVERY_TASK
from app.structured_logging import log_event


logger = logging.getLogger(__name__)


async def enqueue_notification_delivery(
    delivery_id: UUID,
    *,
    countdown: int | None = None,
) -> None:
    """Publish durable delivery work after its database transaction commits."""

    options = {"queue": "email"}
    if countdown is not None:
        options["countdown"] = countdown
    celery_app.send_task(EMAIL_DELIVERY_TASK, args=[str(delivery_id)], **options)
    log_event(
        logger,
        logging.INFO,
        "notification_delivery_queued",
        notification_delivery_id=str(delivery_id),
        retry_delay_seconds=countdown,
    )
