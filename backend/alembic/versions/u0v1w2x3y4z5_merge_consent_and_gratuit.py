"""Merge heads: consent native enum + reduce gratuit minutes

Revision ID: u0v1w2x3y4z5
Revises: c1d2e3f4a5b6, t7u8v9w0x1y2
Create Date: 2026-07-31
"""
from typing import Union

# revision identifiers, used by Alembic.
revision: str = "u0v1w2x3y4z5"
down_revision: Union[str, tuple] = ("c1d2e3f4a5b6", "t7u8v9w0x1y2")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
