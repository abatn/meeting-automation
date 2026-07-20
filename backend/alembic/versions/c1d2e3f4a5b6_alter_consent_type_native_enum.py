"""Alter consent_logs.consent_type from VARCHAR to native ENUM

Phase 163 — Consent Management System (INPDP Art.47 / Art.5 + GDPR).
The original migration created `consent_logs.consent_type` as VARCHAR(20) but
the SQLAlchemy model expects a native `consent_type` ENUM. This migration
converts the column to the native enum. The PG type `consent_type` was already
created idempotently by s6t7u8v9w0x1, so we just alter the column and cast the
existing values (which are already the enum labels C1_AUDIO etc.).

Idempotent: checks current column type before converting.

Revision ID: c1d2e3f4a5b6
Revises: s6t7u8v9w0x1
Create Date: 2026-07-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "s6t7u8v9w0x1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Ensure the native enum type exists (created idempotently in the
    # original consent_logs migration; guard here for safety).
    type_exists = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'consent_type'")
    ).scalar()
    if not type_exists:
        conn.execute(
            sa.text(
                "CREATE TYPE consent_type AS ENUM "
                "('C1_AUDIO', 'C2_VOICE', 'C3_SHARING', 'C4_STORAGE')"
            )
        )

    # Check whether the column is already the native enum.
    col_type = conn.execute(
        sa.text(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_name = 'consent_logs' AND column_name = 'consent_type'"
        )
    ).scalar()

    if col_type == "consent_type":
        # Already a native enum — nothing to do.
        return

    # Convert VARCHAR -> native enum. Existing values are the enum labels
    # (C1_AUDIO etc.), so the cast is safe.
    op.alter_column(
        "consent_logs",
        "consent_type",
        type_=postgresql.ENUM(
            "C1_AUDIO", "C2_VOICE", "C3_SHARING", "C4_STORAGE",
            name="consent_type",
        ),
        postgresql_using="consent_type::consent_type",
        existing_nullable=False,
    )


def downgrade() -> None:
    conn = op.get_bind()
    col_type = conn.execute(
        sa.text(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_name = 'consent_logs' AND column_name = 'consent_type'"
        )
    ).scalar()

    if col_type == "consent_type":
        op.alter_column(
            "consent_logs",
            "consent_type",
            type_=sa.String(20),
            postgresql_using="consent_type::text",
            existing_nullable=False,
        )
