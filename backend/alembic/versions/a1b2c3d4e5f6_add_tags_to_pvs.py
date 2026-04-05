"""add tags column to pvs

Revision ID: a1b2c3d4e5f6
Revises: 0fe164eb0e4a
Create Date: 2026-04-05 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '0fe164eb0e4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pvs', sa.Column('tags', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('pvs', 'tags')
