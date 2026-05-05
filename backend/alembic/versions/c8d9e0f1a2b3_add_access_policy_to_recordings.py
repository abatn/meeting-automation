"""Add access_policy column to recordings table

Revision ID: c8d9e0f1a2b3
Revises: b4c5d6e7f8a9
Create Date: 2026-05-05 13:45:00.000000

This migration adds:
- access_policy column to recordings table (default: 'everyone')
  - everyone: accessible to all team members
  - organizer_only: only organizer can access
  - specific_people: only specific people can access (future: implement access control list)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8d9e0f1a2b3'
down_revision: Union[str, None] = 'c3fe9e232652'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add access_policy column to recordings table
    op.add_column(
        'recordings',
        sa.Column(
            'access_policy',
            sa.String(),
            nullable=False,
            server_default='everyone'
        )
    )
    # Remove the server default after adding the column
    op.alter_column('recordings', 'access_policy', server_default=None)


def downgrade() -> None:
    # Drop the access_policy column
    op.drop_column('recordings', 'access_policy')
