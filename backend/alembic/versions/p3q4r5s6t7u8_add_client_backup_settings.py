"""add client_backup_settings table

Revision ID: p3q4r5s6t7u8
Revises: o3p4q5r6s7t8
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = 'p3q4r5s6t7u8'
down_revision = 'o3p4q5r6s7t8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'backupfrequency') "
        "THEN CREATE TYPE backupfrequency AS ENUM ('none', 'daily', 'weekly', 'monthly'); "
        "END IF; END $$"
    ))
    conn.execute(sa.text(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'backupstorageclass') "
        "THEN CREATE TYPE backupstorageclass AS ENUM ('standard', 'cold', 'archive'); "
        "END IF; END $$"
    ))

    op.create_table(
        'client_backup_settings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('client_id', sa.String(), nullable=False),
        sa.Column('backup_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('backup_frequency', sa.String(), nullable=True),
        sa.Column('backup_retention_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('backup_storage_class', sa.String(), nullable=True),
        sa.Column('include_recordings', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('include_pv', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('max_storage_mb', sa.Integer(), nullable=False, server_default='5120'),
        sa.Column('last_backup_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_client_backup_settings_client_id', 'client_backup_settings', ['client_id'], unique=True)


def downgrade() -> None:
    op.drop_table('client_backup_settings')
    op.execute("DROP TYPE IF EXISTS backupfrequency")
    op.execute("DROP TYPE IF EXISTS backupstorageclass")
