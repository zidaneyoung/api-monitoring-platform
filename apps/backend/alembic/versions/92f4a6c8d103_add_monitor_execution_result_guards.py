"""add monitor execution result guards

Revision ID: 92f4a6c8d103
Revises: f1a9c3e86b42
Create Date: 2026-07-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "92f4a6c8d103"
down_revision: Union[str, Sequence[str], None] = "f1a9c3e86b42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "monitors",
        sa.Column("latest_tls_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_monitor_checks_run_id", "monitor_checks", ["run_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_monitor_checks_run_id", "monitor_checks", type_="unique")
    op.drop_column("monitors", "latest_tls_expires_at")
