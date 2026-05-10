"""add_plan_code_and_minutes_to_pricing_plans

Revision ID: 08439ee30c73
Revises: a24199cc8476
Create Date: 2026-05-10 20:59:18.133291

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "08439ee30c73"
down_revision: Union[str, None] = "a24199cc8476"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add plan_code column (links to SubscriptionPlan enum)
    op.add_column("pricing_plans", sa.Column("plan_code", sa.String(20), nullable=True))
    op.create_index("ix_pricing_plans_plan_code", "pricing_plans", ["plan_code"])
    
    # Add minutes_included column
    op.add_column("pricing_plans", sa.Column("minutes_included", sa.Integer(), nullable=True))
    
    # Seed default values for existing plans
    op.execute("""
        UPDATE pricing_plans SET plan_code = 'GRATUIT', minutes_included = 600 
        WHERE price_monthly = 0 OR LOWER(name::text) LIKE '%gratuit%' OR LOWER(name::text) LIKE '%free%'
    """)
    op.execute("""
        UPDATE pricing_plans SET plan_code = 'PRO', minutes_included = 3000 
        WHERE price_monthly = 99 OR LOWER(name::text) LIKE '%pro%'
    """)
    op.execute("""
        UPDATE pricing_plans SET plan_code = 'ENTREPRISE', minutes_included = 12000 
        WHERE price_monthly = 499 OR LOWER(name::text) LIKE '%enterprise%' OR LOWER(name::text) LIKE '%entreprise%'
    """)


def downgrade() -> None:
    op.drop_index("ix_pricing_plans_plan_code", table_name="pricing_plans")
    op.drop_column("pricing_plans", "plan_code")
    op.drop_column("pricing_plans", "minutes_included")
