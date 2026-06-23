"""Fix facturestatus and suggestionstatus enums: uppercase → lowercase

Python models define these enums with lowercase values, but the DB was created
with uppercase. This migration aligns them.

Revision ID: i3j4k5l6m7n
Revises: h2i3j4k5l6m
Create Date: 2026-06-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i3j4k5l6m7n'
down_revision = 'h2i3j4k5l6m'
branch_labels = None
depends_on = None


def _add_enum_values_and_commit(bind, enum_type, values):
    """Add new enum values in AUTOCOMMIT mode (PostgreSQL requires this)."""
    # Use a separate connection with AUTOCOMMIT to add enum values
    conn = bind.execution_options(isolation_level="AUTOCOMMIT")
    for val in values:
        conn.execute(sa.text(f"ALTER TYPE {enum_type} ADD VALUE IF NOT EXISTS '{val}'"))


def upgrade() -> None:
    bind = op.get_bind()

    # ── Step 1: Add new lowercase values (must commit before using them) ──
    _add_enum_values_and_commit(bind, "facturestatus", ["paid", "pending", "failed", "cancelled"])
    _add_enum_values_and_commit(bind, "suggestionstatus", ["suggested", "accepted", "rejected"])

    # ── Step 2: Migrate data (now safe to use new values) ──
    # facturestatus
    op.execute("UPDATE factures SET status = 'paid' WHERE status = 'PAID'")
    op.execute("UPDATE factures SET status = 'pending' WHERE status = 'PENDING'")
    op.execute("UPDATE factures SET status = 'failed' WHERE status = 'FAILED'")
    op.execute("UPDATE factures SET status = 'cancelled' WHERE status = 'CANCELLED'")

    # suggestionstatus
    op.execute("UPDATE action_suggestions SET status = 'suggested' WHERE status = 'SUGGESTED'")
    op.execute("UPDATE action_suggestions SET status = 'accepted' WHERE status = 'ACCEPTED'")
    op.execute("UPDATE action_suggestions SET status = 'rejected' WHERE status = 'REJECTED'")

    # ── Step 3: Replace enum types (clean up old uppercase values) ──

    # facturestatus
    op.execute("""
        CREATE TYPE facturestatus_new AS ENUM ('paid', 'pending', 'failed', 'cancelled')
    """)
    op.execute("""
        ALTER TABLE factures
        ALTER COLUMN status TYPE facturestatus_new
        USING status::text::facturestatus_new
    """)
    op.execute("DROP TYPE facturestatus")
    op.execute("ALTER TYPE facturestatus_new RENAME TO facturestatus")

    # suggestionstatus
    op.execute("""
        CREATE TYPE suggestionstatus_new AS ENUM ('suggested', 'accepted', 'rejected')
    """)
    op.execute("""
        ALTER TABLE action_suggestions
        ALTER COLUMN status TYPE suggestionstatus_new
        USING status::text::suggestionstatus_new
    """)
    op.execute("DROP TYPE suggestionstatus")
    op.execute("ALTER TYPE suggestionstatus_new RENAME TO suggestionstatus")


def downgrade() -> None:
    # Reverse: lowercase → UPPERCASE
    # Add uppercase values first
    bind = op.get_bind()
    _add_enum_values_and_commit(bind, "facturestatus", ["PAID", "PENDING", "FAILED", "CANCELLED"])
    _add_enum_values_and_commit(bind, "suggestionstatus", ["SUGGESTED", "ACCEPTED", "REJECTED"])

    # Migrate data
    op.execute("UPDATE action_suggestions SET status = 'SUGGESTED' WHERE status = 'suggested'")
    op.execute("UPDATE action_suggestions SET status = 'ACCEPTED' WHERE status = 'accepted'")
    op.execute("UPDATE action_suggestions SET status = 'REJECTED' WHERE status = 'rejected'")
    op.execute("""
        CREATE TYPE suggestionstatus_new AS ENUM ('SUGGESTED', 'ACCEPTED', 'REJECTED')
    """)
    op.execute("""
        ALTER TABLE action_suggestions
        ALTER COLUMN status TYPE suggestionstatus_new
        USING status::text::suggestionstatus_new
    """)
    op.execute("DROP TYPE suggestionstatus")
    op.execute("ALTER TYPE suggestionstatus_new RENAME TO suggestionstatus")

    op.execute("UPDATE factures SET status = 'PAID' WHERE status = 'paid'")
    op.execute("UPDATE factures SET status = 'PENDING' WHERE status = 'pending'")
    op.execute("UPDATE factures SET status = 'FAILED' WHERE status = 'failed'")
    op.execute("UPDATE factures SET status = 'CANCELLED' WHERE status = 'cancelled'")
    op.execute("""
        CREATE TYPE facturestatus_new AS ENUM ('PAID', 'PENDING', 'FAILED', 'CANCELLED')
    """)
    op.execute("""
        ALTER TABLE factures
        ALTER COLUMN status TYPE facturestatus_new
        USING status::text::facturestatus_new
    """)
    op.execute("DROP TYPE facturestatus")
    op.execute("ALTER TYPE facturestatus_new RENAME TO facturestatus")
