"""add database indexes and constraints

Revision ID: a73d1e5c9b04
Revises: f1a9c3e86b42
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a73d1e5c9b04"
down_revision: Union[str, Sequence[str], None] = "f1a9c3e86b42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_monitors_user_id", "monitors", ["user_id"])
    op.create_index(
        "ix_monitors_enabled_next_check_at",
        "monitors",
        ["next_check_at"],
        postgresql_where=sa.text("is_enabled"),
    )
    op.create_index("ix_monitor_checks_run_id", "monitor_checks", ["run_id"])
    op.create_index(
        "ix_incidents_monitor_opened_at",
        "incidents",
        ["monitor_id", "opened_at"],
    )
    op.create_index(
        "ix_incidents_user_opened_at",
        "incidents",
        ["user_id", "opened_at"],
    )
    op.create_index(
        "ix_incidents_triggering_check_id", "incidents", ["triggering_check_id"]
    )
    op.create_index(
        "ix_incidents_recovery_check_id", "incidents", ["recovery_check_id"]
    )
    op.create_index(
        "ix_notification_deliveries_user_id",
        "notification_deliveries",
        ["user_id"],
    )
    op.create_index(
        "ix_notification_deliveries_incident_id",
        "notification_deliveries",
        ["incident_id"],
    )

    op.create_check_constraint(
        "ck_monitor_runs_claimed_started_order",
        "monitor_runs",
        "started_at IS NULL OR claimed_at IS NULL OR started_at >= claimed_at",
    )
    op.create_check_constraint(
        "ck_monitor_runs_started_completed_order",
        "monitor_runs",
        "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
    )
    op.create_check_constraint(
        "ck_notification_deliveries_retry_time_order",
        "notification_deliveries",
        "next_retry_at IS NULL OR last_attempt_at IS NULL "
        "OR next_retry_at >= last_attempt_at",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_notification_deliveries_retry_time_order",
        "notification_deliveries",
        type_="check",
    )
    op.drop_constraint(
        "ck_monitor_runs_started_completed_order", "monitor_runs", type_="check"
    )
    op.drop_constraint(
        "ck_monitor_runs_claimed_started_order", "monitor_runs", type_="check"
    )

    op.drop_index(
        "ix_notification_deliveries_incident_id",
        table_name="notification_deliveries",
    )
    op.drop_index(
        "ix_notification_deliveries_user_id",
        table_name="notification_deliveries",
    )
    op.drop_index("ix_incidents_recovery_check_id", table_name="incidents")
    op.drop_index("ix_incidents_triggering_check_id", table_name="incidents")
    op.drop_index("ix_incidents_user_opened_at", table_name="incidents")
    op.drop_index("ix_incidents_monitor_opened_at", table_name="incidents")
    op.drop_index("ix_monitor_checks_run_id", table_name="monitor_checks")
    op.drop_index("ix_monitors_enabled_next_check_at", table_name="monitors")
    op.drop_index("ix_monitors_user_id", table_name="monitors")
