"""add_consent_logs_table

Revision ID: s6t7u8v9w0x1
Revises: r5s6t7u8v9w0
Create Date: 2026-07-16 16:00:00.000000

"""
# Phase 163 — Consent Management System (INPDP Art.47 / Art.5 + GDPR).
# Consent logs are append-only; withdrawal is recorded via withdrawn_at, never DELETE.
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

from app.models.consent import ConsentType


# revision identifiers, used by Alembic.
revision: str = "s6t7u8v9w0x1"
down_revision: Union[str, None] = "r5s6t7u8v9w0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase 163 — Consent Management System (INPDP Art.47 / Art.5 + GDPR).
    # Both ENUM type and table creation are idempotent so this migration
    # can run on fresh DBs AND on databases where the old main migration
    # (q4r5s6t7u8v9_add_consent_logs.py) already created consent_logs.
    bind = op.get_bind()
    type_exists = bind.execute(
        text("SELECT 1 FROM pg_type WHERE typname = 'consent_type'")
    ).scalar()
    if not type_exists:
        values = ", ".join(f"'{ct.value}'" for ct in ConsentType)
        bind.execute(
            text(f"CREATE TYPE consent_type AS ENUM ({values})")
        )

    table_exists = bind.execute(
        text("SELECT 1 FROM pg_tables WHERE tablename = 'consent_logs'")
    ).scalar()
    if table_exists:
        return

    enum_col = sa.String(20)

    op.create_table(
        "consent_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("consent_type", enum_col, nullable=False),
        sa.Column("consented", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("consent_version", sa.String(), nullable=False, server_default="1.0"),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_logs_id", "consent_logs", ["id"])
    op.create_index("ix_consent_logs_user_id", "consent_logs", ["user_id"])
    op.create_index("ix_consent_logs_client_id", "consent_logs", ["client_id"])
    op.create_index("ix_consent_logs_consent_type", "consent_logs", ["consent_type"])


def downgrade() -> None:
    op.drop_index("ix_consent_logs_consent_type", table_name="consent_logs")
    op.drop_index("ix_consent_logs_client_id", table_name="consent_logs")
    op.drop_index("ix_consent_logs_user_id", table_name="consent_logs")
    op.drop_index("ix_consent_logs_id", table_name="consent_logs")
    op.drop_table("consent_logs")
    bind = op.get_bind()
    type_exists = bind.execute(
        text("SELECT 1 FROM pg_type WHERE typname = 'consent_type'")
    ).scalar()
    if type_exists:
        bind.execute(text("DROP TYPE consent_type"))
