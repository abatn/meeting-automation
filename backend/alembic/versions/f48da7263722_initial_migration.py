"""Initial migration

Revision ID: f48da7263722
Revises: 
Create Date: 2026-02-23 03:22:30.222177

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f48da7263722'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Users Table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=True),
        sa.Column('mfa_secret', sa.String(), nullable=True),
        sa.Column('mfa_enabled', sa.Boolean(), nullable=True),
        sa.Column('role', sa.Enum('DG', 'MANAGER', 'PARTICIPANT', name='userrole'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)

    # 2. Meetings Table
    op.create_table(
        'meetings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('status', sa.Enum('PLANNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', name='meetingstatus'), nullable=True),
        sa.Column('creator_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_meetings_id'), 'meetings', ['id'], unique=False)

    # 3. Meeting Participants Association Table
    op.create_table(
        'meeting_participants',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'meeting_id')
    )

    # 4. Recordings Table
    op.create_table(
        'recordings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('format', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('meeting_id')
    )
    op.create_index(op.f('ix_recordings_id'), 'recordings', ['id'], unique=False)

    # 5. Transcriptions Table
    op.create_table(
        'transcriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('language', sa.String(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('segments', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('meeting_id')
    )
    op.create_index(op.f('ix_transcriptions_id'), 'transcriptions', ['id'], unique=False)

    # 6. PVs Table
    op.create_table(
        'pvs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'VALIDATED', 'SENT', name='pvstatus'), nullable=True),
        sa.Column('validated_by', sa.Integer(), nullable=True),
        sa.Column('validated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ),
        sa.ForeignKeyConstraint(['validated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('meeting_id')
    )
    op.create_index(op.f('ix_pvs_id'), 'pvs', ['id'], unique=False)

    # 7. Actions Table
    op.create_table(
        'actions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('assigned_to', sa.Integer(), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('OPEN', 'IN_PROGRESS', 'COMPLETED', 'DELAYED', name='actionstatus'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], ),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_actions_id'), 'actions', ['id'], unique=False)

    # 8. Audit Logs Table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource', sa.String(), nullable=False),
        sa.Column('resource_id', sa.String(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)

def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('actions')
    op.drop_table('pvs')
    op.drop_table('transcriptions')
    op.drop_table('recordings')
    op.drop_table('meeting_participants')
    op.drop_table('meetings')
    op.drop_table('users')
    # Drop Enums
    sa.Enum(name='userrole').drop(op.get_bind())
    sa.Enum(name='meetingstatus').drop(op.get_bind())
    sa.Enum(name='pvstatus').drop(op.get_bind())
    sa.Enum(name='actionstatus').drop(op.get_bind())