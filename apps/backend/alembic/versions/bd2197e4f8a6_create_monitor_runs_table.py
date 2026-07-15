"""create monitor runs table

Revision ID: bd2197e4f8a6
Revises: 5a7e4d9b2c13
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "bd2197e4f8a6"
down_revision: Union[str, Sequence[str], None] = "5a7e4d9b2c13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "monitor_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("monitor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status", sa.Text(), server_default=sa.text("'queued'"), nullable=False
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
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
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'expired')",
            name="ck_monitor_runs_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0", name="ck_monitor_runs_attempt_count_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["monitor_id"], ["monitors.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "monitor_id", "scheduled_for", name="uq_monitor_runs_monitor_scheduled"
        ),
    )


def downgrade() -> None:
    op.drop_table("monitor_runs")
