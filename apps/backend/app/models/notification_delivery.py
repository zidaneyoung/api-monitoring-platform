from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.incident import Incident
    from app.models.user import User


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "deduplication_key", name="uq_notification_deliveries_deduplication_key"
        ),
        CheckConstraint(
            "status IN ('pending', 'sending', 'delivered', 'retrying', 'failed')",
            name="ck_notification_deliveries_status",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_notification_deliveries_attempt_count_nonnegative",
        ),
        CheckConstraint(
            "length(btrim(event_type)) > 0",
            name="ck_notification_deliveries_event_type_nonempty",
        ),
        CheckConstraint(
            "length(btrim(channel)) > 0",
            name="ck_notification_deliveries_channel_nonempty",
        ),
        CheckConstraint(
            "length(btrim(destination)) > 0",
            name="ck_notification_deliveries_destination_nonempty",
        ),
        CheckConstraint(
            "length(btrim(deduplication_key)) > 0",
            name="ck_notification_deliveries_deduplication_key_nonempty",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default=text("'pending'")
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(Text)
    provider_error_code: Mapped[str | None] = mapped_column(Text)
    provider_error_message: Mapped[str | None] = mapped_column(Text)
    deduplication_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="notification_deliveries")
    incident: Mapped["Incident"] = relationship(
        back_populates="notification_deliveries"
    )
