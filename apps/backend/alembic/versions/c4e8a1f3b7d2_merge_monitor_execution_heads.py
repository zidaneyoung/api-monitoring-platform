"""merge monitor execution migration heads

Revision ID: c4e8a1f3b7d2
Revises: 92f4a6c8d103, e7d4c8a2b1f0
Create Date: 2026-07-17

"""
from typing import Sequence, Union


revision: str = "c4e8a1f3b7d2"
down_revision: Union[str, Sequence[str], None] = (
    "92f4a6c8d103",
    "e7d4c8a2b1f0",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
