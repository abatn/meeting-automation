"""Fix facturestatus and suggestionstatus enums: lowercase to UPPERCASE

Root Cause Analysis (2026-06-22):
  Backend logs showed: invalid input value for enum suggestionstatus: "ACCEPTED"
  and /api/v1/actions/statistics/recurring returned 500.

  The Python models define UPPERCASE enum values (FactureStatus.PAID, SuggestionStatus.ACCEPTED)
  but the PostgreSQL enums were created with lowercase values (paid, accepted).

  This is the SAME pattern as meetingstatus (fixed in l2m3n4o5p6q7).

Affected enums:
  - facturestatus: paid→PAID, pending→PENDING, failed→FAILED, cancelled→CANCELLED
  - suggestionstatus: suggested→SUGGESTED, accepted→ACCEPTED, rejected→REJECTED

Revision ID: n2o3p4q5r6s7
Revises: m1n2o3p4q5r6
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'n2o3p4q5r6s7'
down_revision: Union[str, None] = 'm1n2o3p4q5r6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def _enum_values_uppercase(conn, enum_name: str) -> bool:
    """Check if enum already has UPPERCASE values."""
    result = conn.execute(sa.text(
        "SELECT enumlabel FROM pg_enum "
        "WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = :name) "
        "AND enumlabel = upper(enumlabel)"
    ), {"name": enum_name})
    rows = result.fetchall()
    # If all values are uppercase, no fix needed
    if not rows:
        return True  # enum doesn't exist, skip
    return all(row[0] == row[0].upper() for row in rows)


def upgrade() -> None:
    conn = op.get_bind()

    # --- facturestatus: lowercase → UPPERCASE (idempotent) ---
    if not _enum_values_uppercase(conn, 'facturestatus'):
        op.execute("""
            CREATE TYPE facturestatus_v2 AS ENUM ('PAID', 'PENDING', 'FAILED', 'CANCELLED')
        """)
        op.execute("""
            ALTER TABLE factures
            ALTER COLUMN status TYPE facturestatus_v2
            USING upper(status::text)::facturestatus_v2
        """)
        op.execute("DROP TYPE facturestatus")
        op.execute("ALTER TYPE facturestatus_v2 RENAME TO facturestatus")

    # --- suggestionstatus: lowercase → UPPERCASE (idempotent) ---
    if not _enum_values_uppercase(conn, 'suggestionstatus'):
        op.execute("""
            CREATE TYPE suggestionstatus_v2 AS ENUM ('SUGGESTED', 'ACCEPTED', 'REJECTED')
        """)
        op.execute("""
            ALTER TABLE action_suggestions
            ALTER COLUMN status TYPE suggestionstatus_v2
            USING upper(status::text)::suggestionstatus_v2
        """)
        op.execute("DROP TYPE suggestionstatus")
        op.execute("ALTER TYPE suggestionstatus_v2 RENAME TO suggestionstatus")


def downgrade() -> None:
    conn = op.get_bind()

    # --- suggestionstatus: UPPERCASE → lowercase ---
    if _enum_values_uppercase(conn, 'suggestionstatus'):
        op.execute("""
            CREATE TYPE suggestionstatus_v2 AS ENUM ('suggested', 'accepted', 'rejected')
        """)
        op.execute("""
            ALTER TABLE action_suggestions
            ALTER COLUMN status TYPE suggestionstatus_v2
            USING lower(status::text)::suggestionstatus_v2
        """)
        op.execute("DROP TYPE suggestionstatus")
        op.execute("ALTER TYPE suggestionstatus_v2 RENAME TO suggestionstatus")

    # --- facturestatus: UPPERCASE → lowercase ---
    if _enum_values_uppercase(conn, 'facturestatus'):
        op.execute("""
            CREATE TYPE facturestatus_v2 AS ENUM ('paid', 'pending', 'failed', 'cancelled')
        """)
        op.execute("""
            ALTER TABLE factures
            ALTER COLUMN status TYPE facturestatus_v2
            USING lower(status::text)::facturestatus_v2
        """)
        op.execute("DROP TYPE facturestatus")
        op.execute("ALTER TYPE facturestatus_v2 RENAME TO facturestatus")
