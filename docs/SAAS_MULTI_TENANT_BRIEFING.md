# 🚀 PROJEKT-BRIEFING: Transformation zur Multi-Tenant SaaS-Plattform

## 📌 Übersicht
**Aktueller Stand:** Das Meeting Automation System ist eine voll funktionsfähige Single-Tenant Applikation mit React/TypeScript Frontend, FastAPI Backend, AI Services (Whisper/Mistral), n8n, PostgreSQL, Redis, Minio und ISO 27001 Compliance.

**Ziel:** Die Applikation soll zu einer Multi-Tenant SaaS-Plattform erweitert werden. Jede Firma (Client) bekommt eine eigene isolierte Instanz mit eigenem Dashboard, eigenen Mitarbeitern und eigenen Daten. Der System-Admin erhält ein zentrales Dashboard zur Verwaltung aller Firmen.

---

## 🔍 Baseline Datenbank-Analyse (Stand: 16.03.2026)
Vor Beginn der Umsetzung wurde der Ist-Zustand der Produktion-Datenbank verifiziert:
- **Tabellen-Status:** 85 Tabellen aktiv (inkl. n8n-Workflows).
- **Kern-Tabellen:** Alle Entitäten (users, meetings, actions, pvs, recordings, transcriptions, audit_logs) sind vorhanden und konsistent.
- **Multi-Tenant Check:**
  - `clients` Tabelle muss erstellt werden.
  - `client_id` Spalten müssen in bestehenden Tabellen ergänzt werden.
- **Alembic Status:** Die Baseline für die SaaS-Migration ist die Version `e9dd04c9d6f1`.
- **Ergebnis:** Die Datenbank ist in einem sauberen Ausgangszustand.

---

## 1. Datenbank & Daten-Isolation (Basis)

### 1.1 Neue Tabelle: `clients`
- `id` (uuid, primary key)
- `company_name` (string, unique)
- `subscription_plan` (enum: GRATUIT, PRO, ENTREPRISE)
- `subscription_status` (enum: ACTIVE, DISABLED, PENDING)
- `subscription_start_date` (timestamp)
- `subscription_end_date` (timestamp)
- `billing_cycle` (enum: MONTHLY, YEARLY)
- `minutes_included` (integer)
- `minutes_used` (integer)
- `payment_method` (enum: CARD, TRANSFER, CASH)
- `observations` (text)
- `created_at` (timestamp)
- `updated_at` (timestamp)

### 1.2 Bestehende Tabellen erweitern
Alle folgenden Tabellen bekommen eine `client_id` (foreign key to `clients`):
- `users` (jeder User gehört zu einer Firma)
- `meetings`
- `recordings`
- `transcriptions`
- `pvs` (procès-verbaux)
- `actions`
- `audit_logs`
- `branding_settings`

### 1.3 Row-Level Security (RLS) & Filtering
- Jede Query muss automatisch nach `client_id` filtern.
- Middleware im Backend injiziert die `client_id` aus dem JWT.
- **Mandat:** Striktes Verbot von Cross-Tenant Datenzugriffen.

---

## 2. System-Admin Dashboard

### 2.1 Neue API Endpoints (`/api/v1/admin`)
- `GET /api/v1/admin/clients` - Liste aller Firmen mit Filtern.
- `GET /api/v1/admin/clients/{client_id}` - Client-Details.
- `PATCH /api/v1/admin/clients/{client_id}/status` - Aktivieren/Deaktivieren.
- `GET /api/v1/admin/revenue` - Umsatzstatistiken.

### 2.2 Frontend: Admin Bereich
- Separater Bereich nur für `system_admin`.
- Übersicht über aktive Firmen, Umsatz und System-Performance.
- Verwaltung von Abonnements und Rechnungen.

---

## 3. Provisioning & Onboarding

### 3.1 Onboarding Flow
- Landing Page mit Planauswahl (Gratuit/Pro/Entreprise).
- Automatische Aktivierung bei Online-Zahlung.
- Manuelle Aktivierung durch Admin bei Überweisung/Cash.

### 3.2 Automatische Provisionierung
- Erstellung des Firmen-Admin Accounts.
- Versand der Willkommens-Email.
- Initialisierung des Minuten-Kontingents.

---

## 4. Subscription & Billing

### 4.1 Pläne
- **Gratuit:** Basis-Funktionen, limitiert auf 10 Meetings/Monat.
- **Pro:** Unlimitierte Meetings, KI-Vorschläge, erweiterte Dashboards.
- **Entreprise:** Dedizierter Support, benutzerdefinierte Reports, maximale Sicherheit.

### 4.2 Minuten-Tracking
- Jede Meeting-Minute wird erfasst und vom Kontingent abgezogen.
- Automatisierte Warnungen bei Erreichen des Limits.

---

## 5. Client Dashboard (Firmen-Admin)
- **KPIs:** Meetings, offene Actions, Zeitersparnis durch KI.
- **Benutzerverwaltung:** Einladen von Mitarbeitern, Rollenzuweisung.
- **Abonnement:** Status, verbrauchte Minuten, Rechnungs-Download.
- **Audit-Logs:** Vollständige Historie der Firmenaktivitäten (ISO 27001).

---

## 6. Anpassungen an bestehenden Endpoints

### 6.1 Authentication (JWT)
Das JWT muss erweitert werden um:
- `user_id`
- `client_id`
- `role` (`system_admin`, `client_admin`, `manager`, `participant`)

### 6.2 Globaler Filter-Mechanismus
Implementierung einer Abhängigkeit (`deps.py`), die sicherstellt, dass alle Datenbank-Operationen auf die `client_id` des aktuellen Benutzers eingeschränkt sind.

---

## 7. Deployment & Infrastruktur
- **Kubernetes:** Anpassung der Ingress-Konfiguration für Multi-Tenancy (Subdomains oder Pfade).
- **Backups:** Sicherstellung, dass Backups mandantenfähig und bei Bedarf einzeln wiederherstellbar sind.
