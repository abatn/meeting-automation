"""Alter currency column server_default to TND.

Revision ID: w1x2y3z4a5b6
Revises: v1w2x3y4z5a6
Create Date: 2026-08-01
"""
from typing import Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "w1x2y3z4a5b6"
down_revision: Union[str, None] = "v1w2x3y4z5a6"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Change DB server_default from 'USD' to 'TND'
    # Ensures raw SQL inserts without explicit currency get 'TND'
    op.alter_column(
        "pricing_plans",
        "currency",
        server_default=sa.text("'TND'"),
    )


def downgrade() -> None:
    # Revert to original 'USD' default
    op.alter_column(
        "pricing_plans",
        "currency",
        server_default=sa.text("'USD'"),
    )
