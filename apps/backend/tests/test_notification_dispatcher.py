import asyncio
from unittest.mock import Mock
from uuid import uuid4

from app.notifications.dispatcher import (
    EMAIL_DELIVERY_TASK,
    enqueue_notification_delivery,
)


def test_email_delivery_is_routed_to_the_dedicated_queue(monkeypatch) -> None:
    send_task = Mock()
    monkeypatch.setattr("app.notifications.dispatcher.celery_app.send_task", send_task)
    delivery_id = uuid4()

    asyncio.run(enqueue_notification_delivery(delivery_id))

    send_task.assert_called_once_with(
        EMAIL_DELIVERY_TASK,
        args=[str(delivery_id)],
        queue="email",
    )
