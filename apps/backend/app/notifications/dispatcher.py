from uuid import UUID

from app.celery_app import celery_app
from app.notifications.constants import EMAIL_DELIVERY_TASK


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
