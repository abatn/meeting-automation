"""Add stripe columns to clients (safe, no index drops)

This migration adds the missing stripe_subscription_id and stripe_customer_id
columns to the clients table. It was created because migration 8779f409105a
was stamped but never actually applied (it tries to drop non-existent indexes).

Revision ID: k1l2m3n4o5p6
Revises: j4k5l6m7n8o
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k1l2m3n4o5p6'
down_revision: Union[str, None] = 'j4k5l6m7n8o'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if columns already exist before adding (idempotent)
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'clients' 
        AND column_name IN ('stripe_subscription_id', 'stripe_customer_id')
    """))
    existing_columns = {row[0] for row in result}
    
    if 'stripe_subscription_id' not in existing_columns:
        op.add_column('clients', sa.Column('stripe_subscription_id', sa.String(), nullable=True))
    
    if 'stripe_customer_id' not in existing_columns:
        op.add_column('clients', sa.Column('stripe_customer_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('clients', 'stripe_customer_id')
    op.drop_column('clients', 'stripe_subscription_id')
