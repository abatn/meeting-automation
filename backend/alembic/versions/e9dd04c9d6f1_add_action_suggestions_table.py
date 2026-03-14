"""add_action_suggestions_table

Revision ID: e9dd04c9d6f1
Revises: fb199abdb63a
Create Date: 2026-03-14 00:27:19.128695

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e9dd04c9d6f1'
down_revision: Union[str, None] = 'fb199abdb63a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('action_suggestions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('meeting_id', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('suggested_assignee', sa.String(), nullable=True),
    sa.Column('confidence_score', sa.Float(), nullable=True),
    sa.Column('status', sa.Enum('SUGGESTED', 'ACCEPTED', 'REJECTED', name='suggestionstatus'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_action_suggestions_id'), 'action_suggestions', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_action_suggestions_id'), table_name='action_suggestions')
    op.drop_table('action_suggestions')
    # Drop the enum type created by SQLAlchemy
    op.execute("DROP TYPE IF EXISTS suggestionstatus;")
