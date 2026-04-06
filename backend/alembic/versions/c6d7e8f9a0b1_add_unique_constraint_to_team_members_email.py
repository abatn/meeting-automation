"""Add unique constraint to team_members.email

Revision ID: c6d7e8f9a0b1
Revises: b4c5d6e7f8a9
Create Date: 2026-04-06 00:30:00.000000

This migration enforces email uniqueness in the team_members table.
Combined with the existing deduplication logic in get_team_members() and
create_team_member(), this ensures data integrity at the database level.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c6d7e8f9a0b1'
down_revision: Union[str, None] = 'b4c5d6e7f8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing non-unique index on email
    op.drop_index('ix_team_members_email', table_name='team_members')

    # Create unique index on (client_id, email) for multi-tenant uniqueness
    # This ensures the same email cannot exist twice for the same client
    # Different clients can have contacts with same email (different external people)
    op.create_index('ix_team_members_client_email', 'team_members', ['client_id', 'email'], unique=True)


def downgrade() -> None:
    # Drop unique index
    op.drop_index('ix_team_members_client_email', table_name='team_members')

    # Recreate non-unique index on email only
    op.create_index('ix_team_members_email', 'team_members', ['email'])
