"""Add missing constraints and indices (no-op, already in b4c5d6e7f8a9)

Revision ID: d5e6f7a8b9c0
Revises: abc123def456
Create Date: 2026-05-21 22:03:00.000000

Note: All constraints/indices were already created in b4c5d6e7f8a9.
This migration is kept as a no-op to preserve migration history.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'abc123def456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # All constraints/indices already created in b4c5d6e7f8a9
    pass


def downgrade() -> None:
    # No-op: objects belong to b4c5d6e7f8a9
    pass
