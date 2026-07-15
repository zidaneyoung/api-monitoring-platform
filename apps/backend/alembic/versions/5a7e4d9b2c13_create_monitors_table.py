"""create monitors table

Revision ID: 5a7e4d9b2c13
Revises: e6c06e01a59f
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "5a7e4d9b2c13"
down_revision: Union[str, Sequence[str], None] = "e6c06e01a59f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "monitors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "http_method", sa.Text(), server_default=sa.text("'GET'"), nullable=False
        ),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "expected_status_min",
            sa.SmallInteger(),
            server_default=sa.text("200"),
            nullable=False,
        ),
        sa.Column(
            "expected_status_max",
            sa.SmallInteger(),
            server_default=sa.text("399"),
            nullable=False,
        ),
        sa.Column(
            "failure_threshold",
            sa.SmallInteger(),
            server_default=sa.text("3"),
            nullable=False,
        ),
        sa.Column(
            "recovery_threshold",
            sa.SmallInteger(),
            server_default=sa.text("2"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            server_default=sa.text("'unknown'"),
            nullable=False,
        ),
        sa.Column(
            "is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "consecutive_failures",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "consecutive_successes",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_response_time_ms", sa.Integer(), nullable=True),
        sa.Column("latest_status_code", sa.SmallInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_monitors_name_nonempty"),
        sa.CheckConstraint("length(btrim(url)) > 0", name="ck_monitors_url_nonempty"),
        sa.CheckConstraint(
            "http_method IN ('GET', 'HEAD')", name="ck_monitors_http_method"
        ),
        sa.CheckConstraint(
            "interval_seconds > 0", name="ck_monitors_interval_positive"
        ),
        sa.CheckConstraint("timeout_seconds > 0", name="ck_monitors_timeout_positive"),
        sa.CheckConstraint(
            "expected_status_min BETWEEN 100 AND 599",
            name="ck_monitors_expected_status_min",
        ),
        sa.CheckConstraint(
            "expected_status_max BETWEEN 100 AND 599",
            name="ck_monitors_expected_status_max",
        ),
        sa.CheckConstraint(
            "expected_status_min <= expected_status_max",
            name="ck_monitors_expected_status_range",
        ),
        sa.CheckConstraint(
            "failure_threshold > 0", name="ck_monitors_failure_threshold"
        ),
        sa.CheckConstraint(
            "recovery_threshold > 0", name="ck_monitors_recovery_threshold"
        ),
        sa.CheckConstraint(
            "status IN ('unknown', 'up', 'down', 'paused')",
            name="ck_monitors_status",
        ),
        sa.CheckConstraint(
            "consecutive_failures >= 0", name="ck_monitors_failures_nonnegative"
        ),
        sa.CheckConstraint(
            "consecutive_successes >= 0", name="ck_monitors_successes_nonnegative"
        ),
        sa.CheckConstraint(
            "latest_response_time_ms IS NULL OR latest_response_time_ms >= 0",
            name="ck_monitors_latest_response_time_nonnegative",
        ),
        sa.CheckConstraint(
            "latest_status_code IS NULL OR latest_status_code BETWEEN 100 AND 599",
            name="ck_monitors_latest_status_code",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("monitors")
