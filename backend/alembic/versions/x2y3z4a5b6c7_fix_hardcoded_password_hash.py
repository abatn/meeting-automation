"""fix: correct hardcoded password hash for tidogspot151278@gmail.com

The migration v1w2x3y4z5a6 seeded a user with an incorrect bcrypt hash.
The hash $2b$12$LJ3m4ys3Iz2k... was generated for a different password,
not for Abdelka15121978!. This migration replaces it with the correct
hash generated via get_password_hash('Abdelka15121978!').

IDEMPOTENT: Only updates if the wrong hash is still present.
Production: Contabo (169.58.83.32)
User: tidogspot151278@gmail.com
Reason: Login failed on Production but worked on Staging because Staging
        user was created BEFORE the seed migration (SKIP branch).

Revision ID: x2y3z4a5b6c7
Revises: w1x2y3z4a5b6
Create Date: 2026-08-02
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "x2y3z4a5b6c7"
down_revision: Union[str, None] = "w1x2y3z4a5b6"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

# The INCORRECT hash from migration v1w2x3y4z5a6 (verify_password = False)
WRONG_HASH = "$2b$12$LJ3m4ys3Iz2kfKFRwO0oZOz8VQxKjGZvM3vK2cN9yR1xQ4wE6t8Ae"

# The CORRECT hash generated via get_password_hash('Abdelka15121978!')
# verify_password('Abdelka15121978!', CORRECT_HASH) = True
CORRECT_HASH = "$2b$12$mHZUhbPBxdKpfW1Mh4ufcu84wXYSlMGpyfOTR1f/wb9GyB0JfN0fe"


def upgrade() -> None:
    """Fix incorrect password hash for tidogspot151278@gmail.com.

    Idempotent: Only updates if the wrong hash is still present.
    Uses conn.execute() per project convention (Alembic 2.x).
    """
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE users "
            "SET hashed_password = :correct_hash, updated_at = NOW() "
            "WHERE email = 'tidogspot151278@gmail.com' "
            "AND hashed_password = :wrong_hash"
        ).bindparams(correct_hash=CORRECT_HASH, wrong_hash=WRONG_HASH)
    )


def downgrade() -> None:
    """Revert to the original (incorrect) hash. NOT recommended.

    This is provided for rollback safety only. The original hash
    was never correct for the password Abdelka15121978!.
    Uses conn.execute() per project convention (Alembic 2.x).
    """
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE users "
            "SET hashed_password = :wrong_hash, updated_at = NOW() "
            "WHERE email = 'tidogspot151278@gmail.com' "
            "AND hashed_password = :correct_hash"
        ).bindparams(correct_hash=CORRECT_HASH, wrong_hash=WRONG_HASH)
    )
