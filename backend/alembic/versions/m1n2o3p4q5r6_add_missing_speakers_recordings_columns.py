"""Add missing speakers and recordings columns for staging schema drift

Revision ID: m1n2o3p4q5r6
Revises: l2m3n4o5p6q7
Create Date: 2026-06-22 02:00:00.000000

This migration adds columns that exist in SQLAlchemy models but were never
applied to the staging database due to disconnected migration branches.

Missing from speakers table (7 columns):
  - client_id (FK to clients)
  - resolved_name
  - embedding (JSON)
  - sample_count
  - mapping_confidence
  - mapping_method
  - source

Missing from recordings table (3 columns):
  - access_policy
  - error_message
  - egress_id

All operations use IF NOT EXISTS for safety.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'm1n2o3p4q5r6'
down_revision: Union[str, None] = 'l2m3n4o5p6q7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    result = bind.execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :table AND column_name = :column)"
    ), {"table": table, "column": column})
    return result.scalar()


def upgrade() -> None:
    # === speakers table: 7 missing columns ===
    if not _column_exists('speakers', 'client_id'):
        op.add_column('speakers', sa.Column(
            'client_id', sa.String(),
            sa.ForeignKey('clients.id', ondelete='CASCADE'),
            nullable=True
        ))
        op.create_index('ix_speakers_client_id', 'speakers', ['client_id'])

    if not _column_exists('speakers', 'resolved_name'):
        op.add_column('speakers', sa.Column('resolved_name', sa.String(), nullable=True))

    if not _column_exists('speakers', 'embedding'):
        op.add_column('speakers', sa.Column('embedding', sa.JSON(), nullable=True))

    if not _column_exists('speakers', 'sample_count'):
        op.add_column('speakers', sa.Column('sample_count', sa.Integer(), server_default='0'))

    if not _column_exists('speakers', 'mapping_confidence'):
        op.add_column('speakers', sa.Column('mapping_confidence', sa.Float(), nullable=True))

    if not _column_exists('speakers', 'mapping_method'):
        op.add_column('speakers', sa.Column('mapping_method', sa.String(), nullable=True))

    if not _column_exists('speakers', 'source'):
        op.add_column('speakers', sa.Column('source', sa.String(), server_default='auto_enrolled'))

    # === recordings table: 3 missing columns ===
    if not _column_exists('recordings', 'access_policy'):
        op.add_column('recordings', sa.Column('access_policy', sa.String(), server_default='everyone'))

    if not _column_exists('recordings', 'error_message'):
        op.add_column('recordings', sa.Column('error_message', sa.String(), nullable=True))

    if not _column_exists('recordings', 'egress_id'):
        op.add_column('recordings', sa.Column('egress_id', sa.String(), nullable=True))


def downgrade() -> None:
    # recordings
    if _column_exists('recordings', 'egress_id'):
        op.drop_column('recordings', 'egress_id')
    if _column_exists('recordings', 'error_message'):
        op.drop_column('recordings', 'error_message')
    if _column_exists('recordings', 'access_policy'):
        op.drop_column('recordings', 'access_policy')

    # speakers
    if _column_exists('speakers', 'source'):
        op.drop_column('speakers', 'source')
    if _column_exists('speakers', 'mapping_method'):
        op.drop_column('speakers', 'mapping_method')
    if _column_exists('speakers', 'mapping_confidence'):
        op.drop_column('speakers', 'mapping_confidence')
    if _column_exists('speakers', 'sample_count'):
        op.drop_column('speakers', 'sample_count')
    if _column_exists('speakers', 'embedding'):
        op.drop_column('speakers', 'embedding')
    if _column_exists('speakers', 'resolved_name'):
        op.drop_column('speakers', 'resolved_name')
    if _column_exists('speakers', 'client_id'):
        op.drop_index('ix_speakers_client_id', 'speakers')
        op.drop_column('speakers', 'client_id')
