"""merge_heads_token_hash_and_team_constraint

Revision ID: c3fe9e232652
Revises: add_token_hash_activation, c6d7e8f9a0b1
Create Date: 2026-04-24 02:29:00.356056

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3fe9e232652'
down_revision: Union[str, None] = ('0fe164eb0e4a', 'c6d7e8f9a0b1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass