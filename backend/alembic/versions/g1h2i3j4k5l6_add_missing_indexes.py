"""Add missing indexes for query performance

Revision ID: g1h2i3j4k5l6
Revises: f1a2b3c4d5e6, add_error_message_egress_id
Create Date: 2026-06-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g1h2i3j4k5l6'
down_revision = ('f1a2b3c4d5e6', 'add_error_message_egress_id')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # HIGH IMPACT indexes
    op.create_index('ix_meetings_status', 'meetings', ['status'])
    op.create_index('ix_meetings_start_time', 'meetings', ['start_time'])
    op.create_index('ix_meetings_deleted_at', 'meetings', ['deleted_at'])
    op.create_index('ix_users_client_id', 'users', ['client_id'])
    op.create_index('ix_transcriptions_meeting_id', 'transcriptions', ['meeting_id'])
    op.create_index('ix_transcription_segments_transcription_id', 'transcription_segments', ['transcription_id'])
    op.create_index('ix_speakers_meeting_id', 'speakers', ['meeting_id'])
    op.create_index('ix_recordings_egress_id', 'recordings', ['egress_id'])
    op.create_index('ix_audit_logs_client_timestamp', 'audit_logs', ['client_id', 'timestamp'])
    op.create_index('ix_participants_meeting_id', 'participants', ['meeting_id'])
    
    # MEDIUM IMPACT indexes
    op.create_index('ix_users_deleted_at', 'users', ['deleted_at'])
    op.create_index('ix_users_status', 'users', ['status'])
    op.create_index('ix_pv_sections_pv_id', 'pv_sections', ['pv_id'])
    op.create_index('ix_pv_versions_pv_id', 'pv_versions', ['pv_id'])
    op.create_index('ix_action_assignments_action_id', 'action_assignments', ['action_id'])


def downgrade() -> None:
    op.drop_index('ix_action_assignments_action_id', table_name='action_assignments')
    op.drop_index('ix_pv_versions_pv_id', table_name='pv_versions')
    op.drop_index('ix_pv_sections_pv_id', table_name='pv_sections')
    op.drop_index('ix_users_status', table_name='users')
    op.drop_index('ix_users_deleted_at', table_name='users')
    op.drop_index('ix_participants_meeting_id', table_name='participants')
    op.drop_index('ix_audit_logs_client_timestamp', table_name='audit_logs')
    op.drop_index('ix_recordings_egress_id', table_name='recordings')
    op.drop_index('ix_speakers_meeting_id', table_name='speakers')
    op.drop_index('ix_transcription_segments_transcription_id', table_name='transcription_segments')
    op.drop_index('ix_transcriptions_meeting_id', table_name='transcriptions')
    op.drop_index('ix_users_client_id', table_name='users')
    op.drop_index('ix_meetings_deleted_at', table_name='meetings')
    op.drop_index('ix_meetings_start_time', table_name='meetings')
    op.drop_index('ix_meetings_status', table_name='meetings')
