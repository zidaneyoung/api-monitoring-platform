from datetime import datetime

from app.models import NotificationDelivery
from app.utc import as_utc


class DeliveryTransitionError(ValueError):
    """Raised when a delivery lifecycle transition is not permitted."""


ALLOWED_TRANSITIONS = {
    "pending": frozenset({"sending"}),
    "sending": frozenset({"delivered", "retrying", "failed"}),
    "retrying": frozenset({"sending"}),
    "delivered": frozenset(),
    "failed": frozenset(),
}


def transition_delivery(
    delivery: NotificationDelivery,
    target_status: str,
    *,
    occurred_at: datetime,
    next_retry_at: datetime | None = None,
    provider_message_id: str | None = None,
    provider_error_code: str | None = None,
    provider_error_message: str | None = None,
) -> None:
    occurred_at = as_utc(occurred_at)
    if next_retry_at is not None:
        next_retry_at = as_utc(next_retry_at)
    allowed = ALLOWED_TRANSITIONS.get(delivery.status, frozenset())
    if target_status not in allowed:
        raise DeliveryTransitionError(
            f"delivery cannot transition from {delivery.status} to {target_status}"
        )

    if target_status == "sending":
        delivery.status = "sending"
        delivery.attempt_count += 1
        delivery.last_attempt_at = occurred_at
        delivery.next_retry_at = None
        delivery.provider_error_code = None
        delivery.provider_error_message = None
        return

    if target_status == "delivered":
        delivery.status = "delivered"
        delivery.delivered_at = occurred_at
        delivery.next_retry_at = None
        delivery.provider_message_id = provider_message_id
        delivery.provider_error_code = None
        delivery.provider_error_message = None
        return

    if target_status == "retrying":
        if next_retry_at is None or next_retry_at < occurred_at:
            raise DeliveryTransitionError(
                "retrying deliveries require a future retry time"
            )
        delivery.status = "retrying"
        delivery.next_retry_at = next_retry_at
        delivery.provider_error_code = provider_error_code
        delivery.provider_error_message = provider_error_message
        return

    delivery.status = "failed"
    delivery.next_retry_at = None
    delivery.provider_error_code = provider_error_code
    delivery.provider_error_message = provider_error_message
