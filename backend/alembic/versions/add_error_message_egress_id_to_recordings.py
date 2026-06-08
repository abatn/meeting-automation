"""Add error_message and egress_id to recordings

Revision ID: add_error_message_egress_id
Revises: c8d9e0f1a2b3
Create Date: 2026-06-07 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_error_message_egress_id'
down_revision = 'c8d9e0f1a2b3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('recordings', sa.Column('error_message', sa.String(), nullable=True))
    op.add_column('recordings', sa.Column('egress_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('recordings', 'error_message')
    op.drop_column('recordings', 'egress_id')