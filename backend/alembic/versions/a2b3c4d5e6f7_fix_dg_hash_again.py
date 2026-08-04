"""Fix dg@meeting.tn password hash (second time)

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-08-04

"""
from typing import Union
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'z1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Korrigiert den Hash von dg@meeting.tn FÜR ZWEITES MAL.
    
    Hintergrund:
    - Migration z1a2b3c4d5e6 hat den Hash korrekt gesetzt
    - Aber conftest.py (E2E Tests) hat den Hash überschritten
    - Grund: Gleicher Env-Vars (E2E_TEST_USER_PASSWORD) für zwei verschiedene User
    - conftest.py hat Hash mit Passwort des test-user überschrieben
    
    Lösung:
    - Setzt den Hash zurück auf den korrekten Wert für 'Password123!'
    - conftest.py wirdparallel gefixt (kein Überschreiben mehr)
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
