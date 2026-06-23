"""Fix meetingstatus enum: ensure lowercase values exist, migrate uppercase data, clean up

The initial migration creates the meetingstatus enum with lowercase values (planned, etc.)
but older DBs may have UPPERCASE values (PLANNED, etc.). This migration:
1. Checks if lowercase values exist — adds only missing ones (safe in transactions)
2. Migrates any uppercase data to lowercase
3. Cleans up the enum type to only contain lowercase values

Revision ID: h2i3j4k5l6m
Revises: g1h2i3j4k5l6
Create Date: 2026-06-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h2i3j4k5l6m'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check current state: does the enum have lowercase values already?
    # If so, this migration is a no-op (fresh DB from initial migration)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT enumlabel FROM pg_enum "
        "WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'meetingstatus') "
        "AND enumlabel IN ('planned', 'in_progress', 'completed', 'cancelled')"
    ))
    existing_lowercase = {row[0] for row in result.fetchall()}

    if existing_lowercase == {'planned', 'in_progress', 'completed', 'cancelled'}:
        # Fresh DB — enum already has lowercase values, nothing to do
        return

    # Older DB — may have UPPERCASE values that need conversion
    # Step 1: Migrate data from uppercase to lowercase
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM meetings WHERE status::text IN ('PLANNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')) THEN
                UPDATE meetings SET status = 'planned' WHERE status = 'PLANNED';
                UPDATE meetings SET status = 'in_progress' WHERE status = 'IN_PROGRESS';
                UPDATE meetings SET status = 'completed' WHERE status = 'COMPLETED';
                UPDATE meetings SET status = 'cancelled' WHERE status = 'CANCELLED';
            END IF;
        END $$;
    """)

    # Step 2: Check if UPPERCASE values exist in the enum and clean up
    result = conn.execute(sa.text(
        "SELECT enumlabel FROM pg_enum "
        "WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'meetingstatus') "
        "AND enumlabel IN ('PLANNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')"
    ))
    has_uppercase = len(result.fetchall()) > 0

    if has_uppercase:
        # Recreate enum with only lowercase values
        op.execute("""
            CREATE TYPE meetingstatus_new AS ENUM ('planned', 'in_progress', 'completed', 'cancelled')
        """)
        op.execute("""
            ALTER TABLE meetings
            ALTER COLUMN status TYPE meetingstatus_new
            USING status::text::meetingstatus_new
        """)
        op.execute("DROP TYPE meetingstatus")
        op.execute("ALTER TYPE meetingstatus_new RENAME TO meetingstatus")
    else:
        # Enum has mixed or missing values — ensure lowercase exists
        # Use DO blocks to safely check before adding
        for val in ['planned', 'in_progress', 'completed', 'cancelled']:
            op.execute(f"""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_enum
                        WHERE enumlabel = '{val}'
                        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'meetingstatus')
                    ) THEN
                        ALTER TYPE meetingstatus ADD VALUE '{val}';
                    END IF;
                END $$;
            """)


def downgrade() -> None:
    op.execute("UPDATE meetings SET status = 'PLANNED' WHERE status = 'planned'")
    op.execute("UPDATE meetings SET status = 'IN_PROGRESS' WHERE status = 'in_progress'")
    op.execute("UPDATE meetings SET status = 'COMPLETED' WHERE status = 'completed'")
    op.execute("UPDATE meetings SET status = 'CANCELLED' WHERE status = 'cancelled'")

    op.execute("""
        CREATE TYPE meetingstatus_new AS ENUM ('PLANNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')
    """)
    op.execute("""
        ALTER TABLE meetings
        ALTER COLUMN status TYPE meetingstatus_new
        USING status::text::meetingstatus_new
    """)
    op.execute("DROP TYPE meetingstatus")
    op.execute("ALTER TYPE meetingstatus_new RENAME TO meetingstatus")
