"""Fix dg@meeting.tn password hash

Revision ID: z1a2b3c4d5e6
Revises: x2y3z4a5b6c7
Create Date: 2026-08-03

"""
from typing import Union
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'z1a2b3c4d5e6'
down_revision: Union[str, None] = 'x2y3z4a5b6c7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Korrigiert den Hash von dg@meeting.tn für 'Password123!'
    
    Hintergrund:
    - seed_users.py erstellt den User korrekt mit Hash für 'Password123!'
    - conftest.py (E2E Tests) überschreibt den Hash versehentlich
    - Ergebnis: dg@meeting.tn kann sich nicht mehr einloggen
    
    Lösung:
    - Setzt den Hash zurück auf den korrekten Wert für 'Password123!'
    - Der gleiche Hash wie admin@meeting.tn und user@meeting.tn
    """
    op.execute("""
        UPDATE users 
        SET hashed_password = '$2b$12$3yfYFotgk8fGQp55lp7Sheol83rM9FGrWeNWRRSMBEd9isyqLTopC',
            updated_at = NULL
        WHERE email = 'dg@meeting.tn'
    """)


def downgrade() -> None:
    """
    bcrypt-Hashes sind nicht umkehrbar.
    downgrade() ist absichtlich leer.
    """
    pass
