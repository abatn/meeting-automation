"""Add speaker_mappings and onnx_status to recordings

Revision ID: b5c6d7e8f9a0
Revises: a2b3c4d5e6f7
Create Date: 2026-09-21

"""
from typing import Union
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'b5c6d7e8f9a0'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('recordings', sa.Column('speaker_mappings', sa.JSON, nullable=True))
    op.add_column('recordings', sa.Column('onnx_status', sa.String(), server_default='pending'))


def downgrade() -> None:
    op.drop_column('recordings', 'onnx_status')
    op.drop_column('recordings', 'speaker_mappings')
