"""Reduce GRATUIT plan minutes from 120 to 15.

Revision ID: t7u8v9w0x1y2
Revises: s6t7u8v9w0x1
Create Date: 2026-07-31
"""
from typing import Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "t7u8v9w0x1y2"
down_revision: Union[str, None] = "s6t7u8v9w0x1"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # 1) Normalize pricing_plans: GRATUIT → 15 minutes
    op.execute(
        "UPDATE pricing_plans SET minutes_included = 15 WHERE plan_code = 'GRATUIT'"
    )

    # 2) Normalize existing GRATUIT clients to match new default
    #    (multi-tenant safe: only affects GRATUIT plan, not PRO/ENTREPRISE)
    op.execute(
        "UPDATE clients SET minutes_included = 15 "
        "WHERE subscription_plan = 'GRATUIT'"
    )


def downgrade() -> None:
    # Revert to 120 minutes (previous default)
    op.execute(
        "UPDATE pricing_plans SET minutes_included = 120 WHERE plan_code = 'GRATUIT'"
    )
    op.execute(
        "UPDATE clients SET minutes_included = 120 "
        "WHERE subscription_plan = 'GRATUIT'"
    )
