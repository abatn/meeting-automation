"""add consent_logs table

Revision ID: q4r5s6t7u8v9
Revises: p3q4r5s6t7u8
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa

revision = 'q4r5s6t7u8v9'
down_revision = 'p3q4r5s6t7u8'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'consent_logs',
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('user_id', sa.String, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_id', sa.String, sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('consent_type', sa.String, nullable=False),
        sa.Column('consented', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('consent_version', sa.String, nullable=False, server_default='1.0'),
        sa.Column('ip_address', sa.String, nullable=True),
        sa.Column('user_agent', sa.String, nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('withdrawn_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_consent_logs_client_id', 'consent_logs', ['client_id'])
    op.create_index('ix_consent_logs_user_type', 'consent_logs', ['user_id', 'consent_type'], unique=True)

def downgrade() -> None:
    op.drop_index('ix_consent_logs_user_type', table_name='consent_logs')
    op.drop_index('ix_consent_logs_client_id', table_name='consent_logs')
    op.drop_table('consent_logs')
