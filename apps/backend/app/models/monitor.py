from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.incident import Incident
    from app.models.monitor_check import MonitorCheck
    from app.models.monitor_run import MonitorRun
    from app.models.user import User


class Monitor(Base):
    __tablename__ = "monitors"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="ck_monitors_name_nonempty"),
        CheckConstraint("length(btrim(url)) > 0", name="ck_monitors_url_nonempty"),
        CheckConstraint(
            "http_method IN ('GET', 'HEAD')", name="ck_monitors_http_method"
        ),
        CheckConstraint("interval_seconds > 0", name="ck_monitors_interval_positive"),
        CheckConstraint("timeout_seconds > 0", name="ck_monitors_timeout_positive"),
        CheckConstraint(
            "expected_status_min BETWEEN 100 AND 599",
            name="ck_monitors_expected_status_min",
        ),
        CheckConstraint(
            "expected_status_max BETWEEN 100 AND 599",
            name="ck_monitors_expected_status_max",
        ),
        CheckConstraint(
            "expected_status_min <= expected_status_max",
            name="ck_monitors_expected_status_range",
        ),
        CheckConstraint("failure_threshold > 0", name="ck_monitors_failure_threshold"),
        CheckConstraint(
            "recovery_threshold > 0", name="ck_monitors_recovery_threshold"
        ),
        CheckConstraint(
            "status IN ('unknown', 'up', 'down', 'paused')",
            name="ck_monitors_status",
        ),
        CheckConstraint(
            "consecutive_failures >= 0", name="ck_monitors_failures_nonnegative"
        ),
        CheckConstraint(
            "consecutive_successes >= 0", name="ck_monitors_successes_nonnegative"
        ),
        CheckConstraint(
            "latest_response_time_ms IS NULL OR latest_response_time_ms >= 0",
            name="ck_monitors_latest_response_time_nonnegative",
        ),
        CheckConstraint(
            "latest_status_code IS NULL OR latest_status_code BETWEEN 100 AND 599",
            name="ck_monitors_latest_status_code",
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
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    http_method: Mapped[str] = mapped_column(
        Text, nullable=False, default="GET", server_default=text("'GET'")
    )
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_status_min: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=200, server_default=text("200")
    )
    expected_status_max: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=399, server_default=text("399")
    )
    failure_threshold: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=3, server_default=text("3")
    )
    recovery_threshold: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=2, server_default=text("2")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="unknown", server_default=text("'unknown'")
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    consecutive_successes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_response_time_ms: Mapped[int | None] = mapped_column(Integer)
    latest_status_code: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="monitors")
    runs: Mapped[list["MonitorRun"]] = relationship(
        back_populates="monitor",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    checks: Mapped[list["MonitorCheck"]] = relationship(
        back_populates="monitor",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    incidents: Mapped[list["Incident"]] = relationship(
        back_populates="monitor",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
