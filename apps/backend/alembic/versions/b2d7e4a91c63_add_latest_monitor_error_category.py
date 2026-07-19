"""add latest monitor error category

Revision ID: b2d7e4a91c63
Revises: c4e8a1f3b7d2
Create Date: 2026-07-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2d7e4a91c63"
down_revision: Union[str, Sequence[str], None] = "c4e8a1f3b7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "monitors",
        sa.Column("latest_error_category", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("monitors", "latest_error_category")
