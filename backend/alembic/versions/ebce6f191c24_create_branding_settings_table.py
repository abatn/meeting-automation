"""create_branding_settings_table

Revision ID: ebce6f191c24
Revises: 9f85ae6e2b53
Create Date: 2026-03-10 04:06:19.442140

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ebce6f191c24'
down_revision: Union[str, None] = '9f85ae6e2b53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'branding_settings',
        sa.Column('id', sa.String(), primary_key=True, index=True),
        sa.Column('organization_name', sa.String(), nullable=True),
        sa.Column('logo_url', sa.String(), nullable=True),
        sa.Column('header_text', sa.String(), nullable=True),
        sa.Column('footer_text', sa.String(), nullable=True),
        sa.Column('default_watermark', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('branding_settings')