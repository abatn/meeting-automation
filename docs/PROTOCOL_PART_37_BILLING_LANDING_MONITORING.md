# PROTOKOLL: PART 37 - BILLING, LANDING PAGE & MONITORING (PHASE 4)

**Datum:** 21.03.2026
**Status:** In Arbeit 🔄
**Ziel:** Finalisierung der SaaS-Plattform durch kommerzielle Features, öffentliche Sichtbarkeit und detaillierte System-Überwachung.

## 🚧 OFFENE ROADMAP (Admin-Dashboards)

Diese beiden Dashboards sind interne Administrations-Werkzeuge (nur für System-Admin), die völlig unabhängig von der öffentlichen Landing Page funktionieren. Sie steuern das gesamte System.

### 1. Technik-Dashboard (Priorität 9)
**Funktion:** Überwachung der System-Gesundheit
**Zielgruppe:** Nur System-Admin
**Benötigte Daten:**
- Container-Status (alle Services healthy?)
- Server-Auslastung (CPU, RAM) der Host-Maschine
- API-Latenz und Response-Zeiten
- PostgreSQL-Verbindungen und Query-Performance
- Redis Cache-Hit-Rate
- RabbitMQ Queue-Längen
- Minio Speicherverbrauch
- KI-Services Status (Whisper, Mistral)
- n8n Workflow-Status
- Fehler-Logs und Alerts
**Kommuniziert mit:** Docker API / Kubernetes Metrics Server, PostgreSQL, Redis, RabbitMQ, Minio, KI-Services, n8n API, Logs

### 2. Kunden-Verwaltung Dashboard (Priorität 3 + 6)
**Funktion:** Firmen verwalten + Payment-Integration
**Zielgruppe:** Nur System-Admin
**Benötigte Daten:**
- **Bestehend (Priorität 3):** Alle Firmen mit Status (aktiv/gesperrt/pending), Observations, manuelle Aktivierung bei Virement/Cash
- **Neu (Priorität 6):**
  - Payment-Provider Integration (Stripe/CMI/Payzone) *ohne Mock/Simulation*
  - Rechnungsstellung (automatische Facturen-Generierung)
  - Umsatz pro Firma + Zahlungsstatus
  - Ablaufende Abos + Minuten-Kontingente pro Firma
  - Zahlungshistorie
**Kommuniziert mit:** `clients` Tabelle, `users` Tabelle, `factures` Tabelle, Payment-Provider Webhooks, `usage_minutes` Tabelle

---

## 🎯 BEREITS ERREICHTE ZIELE
- **Billing Infrastruktur (Basis)**: Integration von Rechnungen (`Facture`) und Minuten-Tracking (`UsageMinute`).
- **Public Landing Page**: Moderne Startseite mit Hero-Section, Features, Pricing und CTA für unauthenticated Besucher.

## 📝 DURCHGEFÜHRTE ARBEITSSCHRITTE

### 1. Datenbank & Backend (Basis)
- Neue SQLAlchemy Modelle `Facture` und `UsageMinute` erstellt.
- Migration `ab93febdb189` erfolgreich angewendet.
- Webhook-Router `/api/v1/webhooks/stripe` zur Verarbeitung von Zahlungsereignissen hinzugefügt.

### 2. Frontend (Kunden-Verwaltung Basis UI)
- **Client Details**: Umfassende Ansicht für Admins inkl. Rechnungshistorie und internen Notizen (UI-Vorbereitung).
- **Billing Panel**: Dashboard für Firmen-Admins zum Einsehen des Kontingents und Buchen von Upgrades (UI-Vorbereitung).

### 3. Public Landing Page & Onboarding
- `LandingPage.tsx` erstellt: Vollständiges Marketing-Design (Hero, Features, Multi-language Support, Pricing).
- **RegisterForm**: Neues Formular zur gleichzeitigen Erstellung von Benutzer und Mandant (Firma).

## ⚠️ HERAUSFORDERUNGEN & LÖSUNGEN
- **Kritischer Bugfix (Transcription Pipeline)**: Identifikation eines `IntegrityError` im Celery-Worker. Die `client_id` wurde beim Speichern von Transkriptionen und PVs nicht gesetzt, was zu Fehlern führte. Behoben in `transcription_tasks.py`.
- **Psutil im Container**: Korrektur der `psutil` Abfragen auf nicht-blockierende Aufrufe, um Backend-Hänger zu vermeiden.

## 📊 AKTUELLER STATUS
Die öffentliche Landing Page und die Datenbank-Grundlagen für Multi-Tenancy sind abgeschlossen. Das System erfordert nun die vollständige, code-seitige Ausarbeitung der beiden internen Admin-Dashboards (Technik & Kunden-Verwaltung) gemäß der definierten Roadmap, ohne Rückgriff auf Simulationen.
