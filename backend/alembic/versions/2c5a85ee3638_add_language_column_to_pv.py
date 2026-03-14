"""Add language column to PV

Revision ID: 2c5a85ee3638
Revises: ebce6f191c24
Create Date: 2026-03-13 02:30:57.218260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2c5a85ee3638'
down_revision: Union[str, None] = 'ebce6f191c24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add language column to pvs table
    op.add_column('pvs', sa.Column('language', sa.String(), nullable=False, server_default='fr'))
    # Remove server default after setting it for existing rows
    op.alter_column('pvs', 'language', server_default=None)

    # Standardize column nullability for branding and versions (alignment with models)
    op.alter_column('branding_settings', 'default_watermark',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.alter_column('branding_settings', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.alter_column('pv_versions', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)


def downgrade() -> None:
    op.drop_column('pvs', 'language')
    op.alter_column('pv_versions', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)
    op.alter_column('branding_settings', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.alter_column('branding_settings', 'default_watermark',
               existing_type=sa.BOOLEAN(),
               nullable=True)
