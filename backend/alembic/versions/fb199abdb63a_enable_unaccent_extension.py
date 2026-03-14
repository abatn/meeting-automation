"""Enable unaccent extension

Revision ID: fb199abdb63a
Revises: 2c5a85ee3638
Create Date: 2026-03-13 03:34:53.953835

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fb199abdb63a'
down_revision: Union[str, None] = '2c5a85ee3638'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS unaccent;")
