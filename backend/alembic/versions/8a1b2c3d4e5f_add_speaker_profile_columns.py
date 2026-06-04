"""Add speaker profile columns for speaker identification

Revision ID: 8a1b2c3d4e5f
Revises: e9dd04c9d6f1
Create Date: 2026-06-01 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '8a1b2c3d4e5f'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('speakers', 'meeting_id', nullable=True)
    op.add_column('speakers', sa.Column('client_id', sa.String(), nullable=True))
    op.add_column('speakers', sa.Column('embedding', sa.JSON(), nullable=True))
    op.add_column('speakers', sa.Column('sample_count', sa.Integer(), server_default='0'))
    op.add_column('speakers', sa.Column('mapping_confidence', sa.Float(), nullable=True))
    op.add_column('speakers', sa.Column('mapping_method', sa.String(), nullable=True))
    op.add_column('speakers', sa.Column('source', sa.String(), server_default='auto_enrolled'))

    op.create_foreign_key(
        'fk_speakers_client_id',
        'speakers', 'clients',
        ['client_id'], ['id'],
        ondelete='CASCADE'
    )

    op.create_index('ix_speakers_client_id', 'speakers', ['client_id'])


def downgrade() -> None:
    op.drop_index('ix_speakers_client_id', table_name='speakers')
    op.drop_constraint('fk_speakers_client_id', 'speakers', type_='foreignkey')
    op.drop_column('speakers', 'source')
    op.drop_column('speakers', 'mapping_method')
    op.drop_column('speakers', 'mapping_confidence')
    op.drop_column('speakers', 'sample_count')
    op.drop_column('speakers', 'embedding')
    op.drop_column('speakers', 'client_id')
    op.alter_column('speakers', 'meeting_id', nullable=False)
