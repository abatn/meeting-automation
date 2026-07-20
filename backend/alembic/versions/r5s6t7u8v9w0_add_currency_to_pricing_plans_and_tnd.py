"""add_currency_to_pricing_plans_and_tnd_prices

Revision ID: r5s6t7u8v9w0
Revises: q4r5s6t7u8v9
Create Date: 2026-07-16 14:00:00.000000

"""

# Entscheidung (Kunde 2026-07-16): Landing-Page-Preise werden in TND angezeigt
# (0 / 199 / 399 TND), interne Billing/Stripe-Logik bleibt USD (Stripe unterstützt
# TND nicht als Settlement-Währung). Dies ist eine reine Anzeige-Änderung.
# "Löschen ist verboten" gilt: nur Werte aktualisiert, keine Spalten gelöscht.
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "r5s6t7u8v9w0"
down_revision: Union[str, None] = "q4r5s6t7u8v9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Währungsspalte hinzufügen (Default USD, Anzeige-TND bewusst gesetzt unten)
    op.add_column(
        "pricing_plans",
        sa.Column("currency", sa.String(length=3), nullable=True, server_default="USD"),
    )

    # 2. Monatspreise auf TND-Zielwerte setzen (Anzeige)
    op.execute("UPDATE pricing_plans SET price_monthly = 0 WHERE plan_code = 'GRATUIT'")
    op.execute("UPDATE pricing_plans SET price_monthly = 199 WHERE plan_code = 'PRO'")
    op.execute("UPDATE pricing_plans SET price_monthly = 399 WHERE plan_code = 'ENTREPRISE'")

    # 3. Jahrespreise für Konsistenz anpassen (10x Monatspreis)
    op.execute("UPDATE pricing_plans SET price_yearly = 0 WHERE plan_code = 'GRATUIT'")
    op.execute("UPDATE pricing_plans SET price_yearly = 1990 WHERE plan_code = 'PRO'")
    op.execute("UPDATE pricing_plans SET price_yearly = 3990 WHERE plan_code = 'ENTREPRISE'")

    # 4. Anzeige-Währung auf TND setzen
    op.execute("UPDATE pricing_plans SET currency = 'TND'")


def downgrade() -> None:
    # Preise/USD wiederherstellen (keine Datenvernichtung, nur Werte)
    op.execute("UPDATE pricing_plans SET price_monthly = 0 WHERE plan_code = 'GRATUIT'")
    op.execute("UPDATE pricing_plans SET price_monthly = 99 WHERE plan_code = 'PRO'")
    op.execute("UPDATE pricing_plans SET price_monthly = 499 WHERE plan_code = 'ENTREPRISE'")
    op.execute("UPDATE pricing_plans SET price_yearly = 0 WHERE plan_code = 'GRATUIT'")
    op.execute("UPDATE pricing_plans SET price_yearly = 990 WHERE plan_code = 'PRO'")
    op.execute("UPDATE pricing_plans SET price_yearly = 4990 WHERE plan_code = 'ENTREPRISE'")
    op.execute("UPDATE pricing_plans SET currency = 'USD'")
    op.drop_column("pricing_plans", "currency")
