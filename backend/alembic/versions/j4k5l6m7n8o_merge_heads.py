"""Merge heads: add_stripe_ids_to_clients + meetingstatus fix

Revision ID: j4k5l6m7n8o
Revises: 8779f409105a, h2i3j4k5l6m
Create Date: 2026-06-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'j4k5l6m7n8o'
down_revision = ('8779f409105a', 'h2i3j4k5l6m')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
