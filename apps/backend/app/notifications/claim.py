from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import NotificationDelivery
from app.utc import as_utc


async def claim_notification_delivery(
    delivery_id: UUID,
    *,
    attempted_at: datetime,
    session_factory: async_sessionmaker[AsyncSession],
) -> str:
    """Atomically move one due delivery to sending using PostgreSQL state."""

    attempted_at = as_utc(attempted_at)

    async with session_factory() as session:
        async with session.begin():
            claimed_id = await session.scalar(
                update(NotificationDelivery)
                .where(
                    NotificationDelivery.id == delivery_id,
                    or_(
                        NotificationDelivery.status == "pending",
                        (
                            (NotificationDelivery.status == "retrying")
                            & or_(
                                NotificationDelivery.next_retry_at.is_(None),
                                NotificationDelivery.next_retry_at <= attempted_at,
                            )
                        ),
                    ),
                )
                .values(
                    status="sending",
                    attempt_count=NotificationDelivery.attempt_count + 1,
                    last_attempt_at=attempted_at,
                    next_retry_at=None,
                    provider_error_code=None,
                    provider_error_message=None,
                )
                .returning(NotificationDelivery.id)
            )
            if claimed_id is not None:
                return "claimed"

            state = (
                await session.execute(
                    select(
                        NotificationDelivery.status,
                        NotificationDelivery.next_retry_at,
                    ).where(NotificationDelivery.id == delivery_id)
                )
            ).one_or_none()
    if state is None:
        return "missing"
    status, next_retry_at = state
    if status == "delivered":
        return "already_delivered"
    if status == "sending":
        return "already_claimed"
    if status == "failed":
        return "failed"
    if status == "retrying" and next_retry_at is not None:
        return "not_due"
    return "not_claimable"
