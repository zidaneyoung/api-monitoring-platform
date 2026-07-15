"""create notification deliveries table

Revision ID: f1a9c3e86b42
Revises: d4b8f2c71a30
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f1a9c3e86b42"
down_revision: Union[str, Sequence[str], None] = "d4b8f2c71a30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("destination", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Text(), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column(
            "attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("provider_error_code", sa.Text(), nullable=True),
        sa.Column("provider_error_message", sa.Text(), nullable=True),
        sa.Column("deduplication_key", sa.Text(), nullable=False),
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
            "status IN ('pending', 'sending', 'delivered', 'retrying', 'failed')",
            name="ck_notification_deliveries_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_notification_deliveries_attempt_count_nonnegative",
        ),
        sa.CheckConstraint(
            "length(btrim(event_type)) > 0",
            name="ck_notification_deliveries_event_type_nonempty",
        ),
        sa.CheckConstraint(
            "length(btrim(channel)) > 0",
            name="ck_notification_deliveries_channel_nonempty",
        ),
        sa.CheckConstraint(
            "length(btrim(destination)) > 0",
            name="ck_notification_deliveries_destination_nonempty",
        ),
        sa.CheckConstraint(
            "length(btrim(deduplication_key)) > 0",
            name="ck_notification_deliveries_deduplication_key_nonempty",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deduplication_key", name="uq_notification_deliveries_deduplication_key"
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_deliveries")
