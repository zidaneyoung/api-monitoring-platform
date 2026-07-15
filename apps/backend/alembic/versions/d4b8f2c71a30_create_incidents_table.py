"""create incidents and incident events tables

Revision ID: d4b8f2c71a30
Revises: c8f2a1d4e907
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4b8f2c71a30"
down_revision: Union[str, Sequence[str], None] = "c8f2a1d4e907"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("monitor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status", sa.Text(), server_default=sa.text("'open'"), nullable=False
        ),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "triggering_check_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("recovery_check_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cause_category", sa.Text(), nullable=True),
        sa.Column("cause_message", sa.Text(), nullable=True),
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
            "status IN ('open', 'acknowledged', 'resolved')",
            name="ck_incidents_status",
        ),
        sa.CheckConstraint(
            "acknowledged_at IS NULL OR acknowledged_at >= opened_at",
            name="ck_incidents_acknowledged_time",
        ),
        sa.CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= opened_at",
            name="ck_incidents_resolved_time",
        ),
        sa.ForeignKeyConstraint(
            ["monitor_id"], ["monitors.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["triggering_check_id"], ["monitor_checks.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["recovery_check_id"], ["monitor_checks.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_incidents_one_unresolved_per_monitor",
        "incidents",
        ["monitor_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('open', 'acknowledged')"),
    )

    op.create_table(
        "incident_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sequence_number > 0", name="ck_incident_events_sequence_positive"
        ),
        sa.CheckConstraint(
            "length(btrim(event_type)) > 0",
            name="ck_incident_events_type_nonempty",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "incident_id", "sequence_number", name="uq_incident_events_sequence"
        ),
    )


def downgrade() -> None:
    op.drop_table("incident_events")
    op.drop_index(
        "uq_incidents_one_unresolved_per_monitor", table_name="incidents"
    )
    op.drop_table("incidents")
