from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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
    from app.models.monitor import Monitor
    from app.models.monitor_check import MonitorCheck
    from app.models.user import User


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved')",
            name="ck_incidents_status",
        ),
        CheckConstraint(
            "acknowledged_at IS NULL OR acknowledged_at >= opened_at",
            name="ck_incidents_acknowledged_time",
        ),
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= opened_at",
            name="ck_incidents_resolved_time",
        ),
        Index(
            "uq_incidents_one_unresolved_per_monitor",
            "monitor_id",
            unique=True,
            postgresql_where=text("status IN ('open', 'acknowledged')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    monitor_id: Mapped[UUID] = mapped_column(
        ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="open", server_default=text("'open'")
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    triggering_check_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("monitor_checks.id", ondelete="SET NULL")
    )
    recovery_check_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("monitor_checks.id", ondelete="SET NULL")
    )
    cause_category: Mapped[str | None] = mapped_column(Text)
    cause_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    monitor: Mapped["Monitor"] = relationship(back_populates="incidents")
    user: Mapped["User"] = relationship(back_populates="incidents")
    triggering_check: Mapped["MonitorCheck | None"] = relationship(
        foreign_keys=[triggering_check_id]
    )
    recovery_check: Mapped["MonitorCheck | None"] = relationship(
        foreign_keys=[recovery_check_id]
    )
    events: Mapped[list["IncidentEvent"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="IncidentEvent.sequence_number",
    )


class IncidentEvent(Base):
    __tablename__ = "incident_events"
    __table_args__ = (
        UniqueConstraint(
            "incident_id", "sequence_number", name="uq_incident_events_sequence"
        ),
        CheckConstraint(
            "sequence_number > 0", name="ck_incident_events_sequence_positive"
        ),
        CheckConstraint(
            "length(btrim(event_type)) > 0",
            name="ck_incident_events_type_nonempty",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    incident: Mapped["Incident"] = relationship(back_populates="events")
