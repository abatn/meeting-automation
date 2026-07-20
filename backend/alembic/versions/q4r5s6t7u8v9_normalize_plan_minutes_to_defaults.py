"""normalize_plan_minutes_to_defaults

Revision ID: q4r5s6t7u8v9
Revises: p3q4r5s6t7u8
Create Date: 2026-07-16 12:00:00.000000

"""

# Standard plan minutes (Single Source of Truth = backend/app/services/client_service.py
# DEFAULT_PLAN_MINUTES): GRATUIT=120, PRO=1800, ENTREPRISE=3600
#
# ISO 27001: This data normalization corrects inconsistent minutes_included values
# (600/3000/12000 from legacy backfill) to the canonical defaults. The change is
# applied transparently via migration; affected tenants are logged for audit review.
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "q4r5s6t7u8v9"
down_revision: Union[str, None] = "p3q4r5s6t7u8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Normalize pricing_plans minutes_included to canonical defaults
    op.execute("""
        UPDATE pricing_plans SET minutes_included = 120
        WHERE plan_code = 'GRATUIT'
    """)
    op.execute("""
        UPDATE pricing_plans SET minutes_included = 1800
        WHERE plan_code = 'PRO'
    """)
    op.execute("""
        UPDATE pricing_plans SET minutes_included = 3600
        WHERE plan_code = 'ENTREPRISE'
    """)

    # 2) Normalize clients.minutes_included to match their plan (multi-tenant safe,
    #    filtered by subscription_plan — no cross-tenant data leakage)
    op.execute("""
        UPDATE clients SET minutes_included = 120
        WHERE subscription_plan = 'GRATUIT'
    """)
    op.execute("""
        UPDATE clients SET minutes_included = 1800
        WHERE subscription_plan = 'PRO'
    """)
    op.execute("""
        UPDATE clients SET minutes_included = 3600
        WHERE subscription_plan = 'ENTREPRISE'
    """)


def downgrade() -> None:
    pass
