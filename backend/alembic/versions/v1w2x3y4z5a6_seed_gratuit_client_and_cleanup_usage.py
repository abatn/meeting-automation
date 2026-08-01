"""Seed GRATUIT client + user + cleanup usage_minutes

Revision ID: v1w2x3y4z5a6
Revises: u0v1w2x3y4z5
Create Date: 2026-07-31
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'v1w2x3y4z5a6'
down_revision = 'u0v1w2x3y4z5'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # 1. Cleanup: Delete ALL usage_minutes (stale data from before 15-min limit)
    op.execute("DELETE FROM usage_minutes")

    # 2. Reset minutes_used on ALL clients
    op.execute("UPDATE clients SET minutes_used = 0")

    # 3. Create GRATUIT client if not exists
    client_id = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
    check = conn.execute(
        sa.text("SELECT id FROM clients WHERE id = :id"), {"id": client_id}
    ).fetchone()

    if not check:
        conn.execute(sa.text("""
            INSERT INTO clients (
                id, company_name, subscription_plan, subscription_status,
                subscription_start_date, billing_cycle, minutes_included, minutes_used,
                payment_method, created_at
            ) VALUES (
                :id, 'GRATUIT Test Tenant', 'GRATUIT', 'ACTIVE',
                now(), 'MONTHLY', 15, 0, 'CARD', now()
            )
        """), {"id": client_id})

    # 4. Create GRATUIT test user if not exists
    user_id = 'f1e2d3c4-b5a6-7890-1234-567890abcdef'
    check_user = conn.execute(
        sa.text("SELECT id FROM users WHERE email = :email"),
        {"email": "tidogspot151278@gmail.com"}
    ).fetchone()

    if not check_user:
        # Password: Abdelka15121978! (bcrypt hash)
        hashed = "$2b$12$LJ3m4ys3Iz2kfKFRwO0oZOz8VQxKjGZvM3vK2cN9yR1xQ4wE6t8Ae"
        conn.execute(sa.text("""
            INSERT INTO users (
                id, email, hashed_password, full_name,
                is_superuser, is_mfa_enabled, client_id, status, created_at
            ) VALUES (
                :uid, :email, :pwd, 'Tido Tado',
                false, false, :cid, 'ACTIVE', now()
            )
        """), {"uid": user_id, "email": "tidogspot151278@gmail.com", "pwd": hashed, "cid": client_id})


def downgrade():
    conn = op.get_bind()
    # Remove seeded data
    conn.execute(sa.text("DELETE FROM users WHERE email = :email"), {"email": "tidogspot151278@gmail.com"})
    conn.execute(sa.text("DELETE FROM clients WHERE id = :id"), {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"})
