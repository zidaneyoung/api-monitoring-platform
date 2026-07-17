"""add monitor run enqueue tracking

Revision ID: e7d4c8a2b1f0
Revises: a73d1e5c9b04
Create Date: 2026-07-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7d4c8a2b1f0"
down_revision: Union[str, Sequence[str], None] = "a73d1e5c9b04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "monitor_runs",
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_monitor_runs_pending_dispatch",
        "monitor_runs",
        ["enqueued_at"],
        postgresql_where=sa.text("status = 'queued' AND enqueued_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_monitor_runs_pending_dispatch", table_name="monitor_runs")
    op.drop_column("monitor_runs", "enqueued_at")
