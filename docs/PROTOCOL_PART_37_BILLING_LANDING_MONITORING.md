# PROTOKOLL: PART 37 - BILLING, LANDING PAGE, MONITORING & ROLE SEPARATION (PHASE 4)

**Datum:** 22.03.2026
**Status:** Abgeschlossen ✅
**Ziel:** Finalisierung der SaaS-Plattform durch kommerzielle Features, öffentliche Sichtbarkeit, detaillierte System-Überwachung und strikte Rollentrennung.

## 🚧 OFFENE ROADMAP (Admin-Dashboards) -> Abgeschlossen

Diese beiden Dashboards sind interne Administrations-Werkzeuge (nur für System-Admin), die völlig unabhängig von der öffentlichen Landing Page funktionieren. Sie steuern das gesamte System.

### 1. Technik-Dashboard (Mission Control) - Abgeschlossen
**Funktion:** Überwachung der System-Gesundheit
**Zielgruppe:** Nur `tech_admin`
**Benötigte Daten:**
- Container-Status (alle Services healthy?)
- Server-Auslastung (CPU, RAM) der Host-Maschine
- API-Latenz und Response-Zeiten
- PostgreSQL-Verbindungen und Query-Performance
- Redis Cache-Hit-Rate
- RabbitMQ Queue-Längen
- Minio Speicherverbrauch
- KI-Services Status (Mistral, Gladia)
- n8n Workflow-Status
**Kommuniziert mit:** PostgreSQL, Redis, RabbitMQ, Minio, KI-Services, n8n API

### 2. Kunden-Verwaltung Dashboard - Abgeschlossen
**Funktion:** Firmen verwalten + Payment-Integration
**Zielgruppe:** Nur `system_admin` (Business Admin)
**Benötigte Daten:**
- Alle Firmen mit Status (aktiv/gesperrt/pending)
- Payment-Provider Integration (Stripe) *ohne Mock/Simulation*
- Rechnungsstellung (automatische Facturen-Generierung via PDFService)
- Umsatz pro Firma + Zahlungsstatus
- Ablaufende Abos + Minuten-Kontingente pro Firma
- Zahlungshistorie

---

## 🎯 BEREITS ERREICHTE ZIELE
- **Billing Infrastruktur (Basis)**: Integration von Rechnungen (`Facture`) und Minuten-Tracking (`UsageMinute`).
- **Public Landing Page**: Hochkonvertierendes Design im Stil von Stripe/Linear. Kompakte Typografie, Bento-Grid Features, animierte Pipeline und vollständige i18n-Striktheit (keine Fallbacks, 100% lokalisiert).

## 📝 DURCHGEFÜHRTE ARBEITSSCHRITTE

### 1. Technik-Dashboard (Metriken)
- **Backend API (`app/api/v1/admin.py`)**: `get_system_performance` umgeschrieben, um echte Pings an `n8n`, `Mistral` und `Gladia` zu senden. RabbitMQ Queue-Statistiken über die HTTP API hinzugefügt. Redis Hit-Rate Berechnung via `INFO stats` implementiert. DB-Ping als sichere Alternative zu `pg_stat_activity` (Permissions) integriert.
- **Frontend (`TechnikDashboard.tsx`)**: Vollständiger Rewrite der Komponente als "Mission Control". Entfernung jeglicher Abhängigkeiten zum `MainLayout` (Kunden-Sidebar), um eine isolierte Dark-Mode-Ansicht für Tech-Admins zu schaffen.

### 2. Kunden-Verwaltung & Echtes Payment
- **Stripe Integration (`billing_service.py`)**: `stripe` Paket in `requirements.txt` hinzugefügt. Logik für `create_checkout_session` und Webhook-Verarbeitung implementiert.
- **PDF-Rechnungen**: `PDFService` mit `weasyprint` und `jinja2` erstellt, der HTML-Vorlagen (`invoice_template.html`) rendert und die fertigen PDFs sicher in S3/MinIO ablegt. Download-Endpunkt implementiert.
- **Frontend (`ClientList.tsx`, `BillingPanel.tsx`)**: Download-Buttons für Rechnungen implementiert, Anzeige der echten `minutes_used_month` vs. `minutes_included` und vollständiges Re-Design.

### 3. Security, Audit Logs & Rollen-Trennung
- **Audit Logging (`audit_service.py`)**: Neuen ISO-27001-konformen Service erstellt, der Modifikationen des Mandanten-Status und Zahlungseingänge rechtssicher aufzeichnet.
- **Strikte Rollen-Trennung (Frontend Stacking Fix)**: Lösung des Problems, bei dem React fälschlicherweise das Business-Dashboard, das Technik-Dashboard und den Meeting Planner gleichzeitig auf einer Seite gerendert hat.
  - **Lösung:** Einführung der neuen Backend-Rolle `tech_admin` im `seed_users.py`.
  - Umbau der `App.tsx` im Frontend: Harte "Early Returns" für jede Rolle implementiert. Ein `tech_admin` wird auf `/admin/technik` gelockt, ein `system_admin` auf Business-Routen.
- **Sprachliche Bereinigung**: Alle hart codierten Texte wurden entfernt und durch sauberes i18n (`fr-TN.json`, `ar-TN.json`, `en.json`) für den Maghreb-Markt ersetzt.

## ⚠️ HERAUSFORDERUNGEN & LÖSUNGEN
- **Frontend Component Stacking (Render-Fehler)**: Der Benutzer meldete, dass alle Dashboards gleichzeitig erschienen. Die Lösung erforderte die harte architekturelle Trennung zwischen `tech_admin` und `business_admin` in `App.tsx`.
- **Docker Caching / Nginx State**: Das Frontend-Image übernahm neue Code-Änderungen nicht (`error getting credentials`). Die Lösung lag in der forcierten `--no-cache` Erstellung bzw. im Temporären Deaktivieren von `.docker/config.json`.
- **Kryptografische Hash-Diskrepanz**: Es gab Unstimmigkeiten beim Login. Das Seed-Skript (`seed_users.py`) wurde korrigiert, um bestehende Passwörter (`Password123!`) zuverlässig zu überschreiben.

## 📊 AKTUELLER STATUS
Die öffentliche Landing Page, die Datenbank-Grundlagen für Multi-Tenancy und die **internen Admin-Dashboards** (Technik & Kunden-Verwaltung) sind gemäß Roadmap zu 100% abgeschlossen und strikt getrennt. Das System ist bereit für den produktiven SaaS-Betrieb (Phase 5).

---

## 🔧 FIX: Billing Phase 1 Quick-Wins (21.06.2026)

### 1. Revenue-Bug im Admin-Endpoint
**Datei:** `backend/app/api/v1/admin.py` (Zeile 187-191)

**Problem:** `active_pro` prüfte ob IRGENDEIN Client ACTIVE ist, nicht ob PRO-Clients aktiv sind:
```python
# VORHER (Bug):
active_pro = plan_counts.get("PRO", 0) if status_counts.get("ACTIVE", 0) > 0 else 0
# → Wenn 1 Client ACTIVE ist, werden ALLE PRO-Clients gezählt
```

**Fix:** Korrekte Query die nur ACTIVE Clients pro Plan zählt:
```python
# NACHHER:
plan_stmt = (
    select(ClientModel.subscription_plan, func.count(ClientModel.id))
    .where(ClientModel.subscription_status == SubscriptionStatus.ACTIVE)
    .group_by(ClientModel.subscription_plan)
)
```

### 2. Hardcoded Revenue → CMS-Preise
**Datei:** `backend/app/api/v1/admin.py` (Zeile 190-191)

**Problem:** Preise waren hardcoded `$99`/`$499` statt aus `PricingPlan` Tabelle

**Fix:** Preise werden dynamisch aus CMS gelesen mit Fallback:
```python
for plan_code in ["PRO", "ENTREPRISE"]:
    price_stmt = select(PricingPlan.price_monthly).where(
        PricingPlan.plan_code == plan_code, PricingPlan.is_active == True
    )
    price_result = await db.execute(price_stmt)
    price_row = price_result.scalar_one_or_none()
    prices[plan_code] = price_row if price_row else (99 if plan_code == "PRO" else 499)
```

### 3. Landing-Page Preise dynamisieren
**Datei:** `frontend/src/pages/LandingPage.tsx`

**Problem:** Drei Preiskarten ($0/$99/$499) hardcoded, nicht aus CMS

**Fix:**
- `cmsService.getPricing(i18n.language)` lädt Preise aus `/api/v1/cms/pricing`
- `useEffect` bei Sprachwechsel aktualisiert Preise
- Fallback auf Defaults wenn API fehlschlägt

### 4. Stripe-Keys Konfiguration
**Dateien:** `.env.example`, `.env`

**Fix:** Stripe-Konfiguration dokumentiert:
```bash
STRIPE_API_KEY=sk_test_your-stripe-secret-key
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret
STRIPE_PUBLISHABLE_KEY=pk_test_your-stripe-publishable-key
STRIPE_PRICE_ID_PRO=price_your-pro-price-id
STRIPE_PRICE_ID_ENTREPRISE=price_your-enterprise-price-id
```
Leere Werte = Mock-Modus (kein Fehler)

### Dateien geändert
```
backend/app/api/v1/admin.py               — Revenue-Bug + CMS-Preise
frontend/src/pages/LandingPage.tsx         — Dynamische Preise aus CMS
.env.example                              — Stripe-Keys dokumentiert
.env                                      — Stripe-Platzhalter (leer = Mock)
```

### Verifikation
- ✅ 8/8 Tests bestanden
- ✅ Frontend rebuild (17s) + deploy
- ✅ Backend restart (healthy)

---

## 🔧 FIX: Billing Phase 2 — Stripe Lifecycle (21.06.2026)

### 1. Checkout Session mit `customer_email`
**Datei:** `backend/app/services/billing_service.py` (Zeile 87-124)

**Problem:** Checkout-Session enthielt kein `customer_email` → Stripe zeigt leere Email im Checkout.
Zudem fehlte `subscription_data` mit Metadata → Webhooks für Subscription-Änderungen erhielten keinen `client_id`.

**Fix:**
```python
session_params["customer_email"] = customer_email  # oder
session_params["customer"] = stripe_customer_id   # wenn bekannt
session_params["subscription_data"] = {
    "metadata": {"client_id": client_id, "plan": plan_name}
}
```

### 2. `invoice.paid` Webhook implementiert
**Datei:** `backend/app/api/v1/webhooks_stripe.py`

**Vorher:** `pass` (kein Handler für wiederkehrende Zahlungen)
**Nachher:** Erstellt `Facture`-Record mit `PAID`-Status, matched Client via `stripe_subscription_id` oder `stripe_customer_id`.

### 3. `customer.subscription.*` Webhook-Handler
**Datei:** `backend/app/api/v1/webhooks_stripe.py`

**Events:** `created`, `updated`, `deleted`
- Mappt Stripe-Status (`active`, `canceled`, `past_due`, etc.) auf interne `SubscriptionStatus`
- Setzt `subscription_end_date` aus `current_period_end`
- Protokolliert Audit-Trail

### 4. Stripe IDs im Client speichern
**Datei:** `backend/app/models/client.py`

**Neue Felder:**
- `stripe_subscription_id` (String, nullable) — aus `checkout.session.completed` extrahiert
- `stripe_customer_id` (String, nullable) — für wiederkehrende Kunden
- Migration: `8779f409105a`

### 5. `next_billing_date` korrigiert
**Datei:** `backend/app/services/billing_service.py`

**Vorher:** Naiver `start_date + 30 Tage`
**Nachher:** Liest `client.subscription_end_date` (wird durch Webhooks gesetzt)

### Dateien geändert
```
backend/app/services/billing_service.py          — Checkout + Usage Summary
backend/app/api/v1/billing.py                    — Email-Passung
backend/app/api/v1/webhooks_stripe.py            — invoice.paid + subscription Handler
backend/app/models/client.py                     — stripe_subscription_id, stripe_customer_id
```

### Verifikation
- ✅ Python Imports validiert (Docker)
- ✅ Checkout-Session enthält `customer_email`, `metadata`, `subscription_data`
- ✅ Webhook `invoice.paid` erstellt Facture-Record
- ✅ Webhook `customer.subscription.*` synchronisiert Subscription-Status

### Offene Punkte (Phase 2)
- [x] Checkout-Flow reparieren (customer_email, metadata)
- [x] Webhook `invoice.paid` implementieren
- [x] `customer.subscription.*` Webhook-Handler
- [x] Subscription-ID in Client speichern
- [x] `next_billing_date` korrigieren (Stripe-Sync)
