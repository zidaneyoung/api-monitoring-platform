from uuid import UUID

from app.celery_app import celery_app
from app.notifications.constants import EMAIL_DELIVERY_TASK


async def enqueue_notification_delivery(delivery_id: UUID) -> None:
    """Publish durable delivery work after its database transaction commits."""

    celery_app.send_task(
        EMAIL_DELIVERY_TASK,
        args=[str(delivery_id)],
        queue="email",
    )
