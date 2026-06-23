"""Fix meetingstatus enum: replace lowercase values with uppercase

The Python model defines UPPERCASE enum values (PLANNED, IN_PROGRESS, etc.)
but the initial migration creates lowercase (planned, in_progress, etc.).
This migration replaces the enum type to use UPPERCASE matching the model.

Idempotent: checks current state before converting.

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'l2m3n4o5p6q7'
down_revision: Union[str, None] = 'k1l2m3n4o5p6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check if enum already has UPPERCASE values
    result = conn.execute(sa.text(
        "SELECT enumlabel FROM pg_enum "
        "WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'meetingstatus') "
        "AND enumlabel IN ('PLANNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')"
    ))
    existing_uppercase = {row[0] for row in result.fetchall()}

    if existing_uppercase == {'PLANNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'}:
        # Already UPPERCASE — nothing to do
        return

    # Enum has lowercase values (or mixed) — convert to UPPERCASE
    # 1. Create new enum type with UPPERCASE values (matching Python model)
    op.execute("""
        CREATE TYPE meetingstatus_v2 AS ENUM ('PLANNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')
    """)

    # 2. Convert column: cast via upper() to transform lowercase→UPPERCASE in one step
    op.execute("""
        ALTER TABLE meetings
        ALTER COLUMN status TYPE meetingstatus_v2
        USING upper(status::text)::meetingstatus_v2
    """)

    # 3. Drop old type and rename new
    op.execute("DROP TYPE meetingstatus")
    op.execute("ALTER TYPE meetingstatus_v2 RENAME TO meetingstatus")


def downgrade() -> None:
    op.execute("""
        CREATE TYPE meetingstatus_v2 AS ENUM ('planned', 'in_progress', 'completed', 'cancelled')
    """)
    op.execute("""
        ALTER TABLE meetings
        ALTER COLUMN status TYPE meetingstatus_v2
        USING lower(status::text)::meetingstatus_v2
    """)
    op.execute("DROP TYPE meetingstatus")
    op.execute("ALTER TYPE meetingstatus_v2 RENAME TO meetingstatus")
