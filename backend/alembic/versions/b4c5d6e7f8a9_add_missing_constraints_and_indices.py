"""Add missing constraints and indices for production stability

Revision ID: b4c5d6e7f8a9
Revises: a1b2c3d4e5f6
Create Date: 2026-04-05 20:30:00.000000

This migration adds:
- n8n_meetings table (for n8n meeting-created workflow)
- UNIQUE constraint on participants(meeting_id, email) (prevent duplicates)
- CHECK constraint on meetings(end_time > start_time) (data integrity)
- Index on actions(meeting_id, status) (performance)
- Index on action_assignments(user_id) (performance)
- Index on recordings(meeting_id, status) (performance)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. n8n_meetings table (for n8n meeting-created workflow persistence)
    op.create_table(
        'n8n_meetings',
        sa.Column('id', sa.String(), primary_key=True, index=True),
        sa.Column('meeting_id', sa.String(), sa.ForeignKey('meetings.id'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )

    # 2. UNIQUE constraint on participants(meeting_id, email)
    # Prevents duplicate participant entries for same meeting+email combination
    op.create_unique_constraint('uq_participants_meeting_email', 'participants', ['meeting_id', 'email'])

    # 3. CHECK constraint on meetings: end_time must be after start_time (or NULL)
    # Using plain SQL expression for compatibility
    op.create_check_constraint(
        'ck_meeting_end_after_start',
        'meetings',
        'end_time IS NULL OR end_time > start_time'
    )

    # 4. Index on actions(meeting_id, status) - for dashboard queries and filtering
    op.create_index('ix_actions_meeting_status', 'actions', ['meeting_id', 'status'])

    # 5. Index on action_assignments(user_id) - for finding actions assigned to a user quickly
    op.create_index('ix_action_assignments_user_id', 'action_assignments', ['user_id'])

    # 6. Index on recordings(meeting_id, status) - for meeting recordings lookup and status filtering
    op.create_index('ix_recordings_meeting_status', 'recordings', ['meeting_id', 'status'])


def downgrade() -> None:
    # Drop in reverse order
    op.drop_index('ix_recordings_meeting_status', table_name='recordings')
    op.drop_index('ix_action_assignments_user_id', table_name='action_assignments')
    op.drop_index('ix_actions_meeting_status', table_name='actions')
    op.drop_constraint('ck_meeting_end_after_start', 'meetings', type_='check')
    op.drop_constraint('uq_participants_meeting_email', 'participants', type_='unique')
    op.drop_table('n8n_meetings')
