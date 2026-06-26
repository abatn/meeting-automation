"""Add room_participants to recordings for LiveKit Identity Speaker ID

Revision ID: o3p4q5r6s7t8
Revises: n2o3p4q5r6s7
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "o3p4q5r6s7t8"
down_revision = "n2o3p4q5r6s7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("recordings")]
    if "room_participants" not in columns:
        op.add_column(
            "recordings",
            sa.Column("room_participants", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("recordings", "room_participants")
