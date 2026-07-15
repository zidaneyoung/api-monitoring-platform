"""create monitor checks table

Revision ID: c8f2a1d4e907
Revises: bd2197e4f8a6
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c8f2a1d4e907"
down_revision: Union[str, Sequence[str], None] = "bd2197e4f8a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "monitor_checks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("monitor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("http_status_code", sa.SmallInteger(), nullable=True),
        sa.Column("error_category", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("tls_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "completed_at >= started_at", name="ck_monitor_checks_time_order"
        ),
        sa.CheckConstraint(
            "response_time_ms IS NULL OR response_time_ms >= 0",
            name="ck_monitor_checks_response_time_nonnegative",
        ),
        sa.CheckConstraint(
            "http_status_code IS NULL OR http_status_code BETWEEN 100 AND 599",
            name="ck_monitor_checks_http_status_code",
        ),
        sa.ForeignKeyConstraint(
            ["monitor_id"], ["monitors.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["monitor_runs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_monitor_checks_monitor_started_at",
        "monitor_checks",
        ["monitor_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_monitor_checks_monitor_started_at", table_name="monitor_checks"
    )
    op.drop_table("monitor_checks")
