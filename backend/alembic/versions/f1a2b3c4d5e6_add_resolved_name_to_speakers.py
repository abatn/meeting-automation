"""add resolved_name to speakers

Revision ID: f1a2b3c4d5e6
Revises: 8a1b2c3d4e5f
Create Date: 2026-06-03 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = '8a1b2c3d4e5f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('speakers', sa.Column('resolved_name', sa.String(), nullable=True))
    # Backfill: for existing profiles where name is a resolved name (not "Speaker N")
    op.execute(
        "UPDATE speakers SET resolved_name = name WHERE name NOT LIKE 'Speaker %'"
    )


def downgrade() -> None:
    op.drop_column('speakers', 'resolved_name')
