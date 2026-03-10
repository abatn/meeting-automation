"""create_pv_versions_table

Revision ID: 9f85ae6e2b53
Revises: 63f88d2a653f
Create Date: 2026-03-10 03:54:34.747466

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f85ae6e2b53'
down_revision: Union[str, None] = '63f88d2a653f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pv_versions',
        sa.Column('id', sa.String(), primary_key=True, index=True),
        sa.Column('pv_id', sa.String(), sa.ForeignKey('pvs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('snapshot_data', sa.Text(), nullable=False),
        sa.Column('change_summary', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('created_by_id', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('pv_versions')