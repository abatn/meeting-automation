"""add_user_status_and_activation_token

Revision ID: 0fe164eb0e4a
Revises: 4fb76575fee0
Create Date: 2026-04-01 15:31:52.994471

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0fe164eb0e4a'
down_revision: Union[str, None] = '4fb76575fee0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safely add the status column and populate it before making it NOT NULL
    op.add_column('users', sa.Column('status', sa.String(), nullable=True))
    op.execute("UPDATE users SET status = 'ACTIVE' WHERE is_active = true")
    op.execute("UPDATE users SET status = 'DISABLED' WHERE is_active = false")
    op.alter_column('users', 'status', nullable=False)
    op.drop_column('users', 'is_active')

    # Create activation_tokens table
    op.create_table('activation_tokens',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('token', sa.String(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_activation_tokens_id'), 'activation_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_activation_tokens_token'), 'activation_tokens', ['token'], unique=True)


def downgrade() -> None:
    # Drop activation_tokens table
    op.drop_index(op.f('ix_activation_tokens_token'), table_name='activation_tokens')
    op.drop_index(op.f('ix_activation_tokens_id'), table_name='activation_tokens')
    op.drop_table('activation_tokens')

    # Revert users table
    op.add_column('users', sa.Column('is_active', sa.BOOLEAN(), autoincrement=False, nullable=True))
    op.execute("UPDATE users SET is_active = true WHERE status = 'ACTIVE'")
    op.execute("UPDATE users SET is_active = false WHERE status != 'ACTIVE'")
    op.alter_column('users', 'is_active', nullable=False)
    op.drop_column('users', 'status')