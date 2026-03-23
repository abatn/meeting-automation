# AI Session Context - Meeting Automation System

**WICHTIG FÜR DEN KI-AGENTEN**: Lese diese Datei zu Beginn JEDER neuen Session, um den Projektstatus, die Architektur und die nächsten Aufgaben sofort zu verstehen.

## 1. Projektübersicht
Ein mehrsprachiges (Arabisch, Französisch, Englisch) Meeting-Management-System, das Audio aufnimmt, transkribiert, Protokolle (PVs) generiert und Teilnehmer benachrichtigt. Der Fokus liegt auf Sicherheit (ISO 27001) und Stabilität.

## 2. Technologie-Stack & Architektur
*   **Frontend**: React 18, Vite, TypeScript, MUI, i18next. Rollenbasierte Dashboards (DG, Manager, Participant). Vollständig lokalisiert (RTL-Arabisch, Französisch, Englisch).
*   **Backend**: FastAPI, Python 3.11, Pydantic. API-Endpunkte für Auth, Meetings, Transkriptionen, Berichte.
*   **Datenbanken**: PostgreSQL 15 (verwaltet über SQLAlchemy 2.0/Alembic) für persistente Daten.
*   **Storage**: MinIO (S3-kompatibel) für die sichere Speicherung von Audio-Chunks und PDF-Dokumenten.
*   **Message Broker & Cache**: RabbitMQ als Broker für Celery. Redis als Result-Backend, Token-Blacklist (Sicherheit) und WebSocket-Pub/Sub.
*   **Asynchrone Pipeline**: Celery-Worker verwalten langlaufende Prozesse (KI-Aufrufe, E-Mail-Schedules). Die `asyncio`-Event-Loop-Verwaltung in Celery ist manuell abgesichert, um `RuntimeError` zu vermeiden.

## 3. Die KI-Pipeline (Der Kern-Workflow)
Die Pipeline nutzt den modernen **Gladia V2** Service für maximale Stabilität und Präzision.
1.  **Audio-Upload**: Frontend streamt Audio-Chunks zu MinIO.
2.  **Celery-Trigger**: Nach Abschluss startet die Task `process_recording`.
3.  **Gladia V2 Pipeline**: Der Worker nutzt den `GladiaService` (asynchroner 3-Stufen-Prozess: Upload -> Pre-recorded Request -> Polling). Gladia liefert Transkription und **Speaker Diarization** in einem Schritt.
4.  **PV-Generierung**: Der formatierte Text (inkl. Sprecher-Labels) geht an **Mistral AI (`mistral-large-latest`)**. Mistral liefert ein striktes JSON.
5.  **ML Action Suggestions**: Parallel zur PV-Erstellung generiert Mistral implizite Aufgabenvorschläge, die in der Tabelle `action_suggestions` gespeichert werden.
6.  **Datenbank-Speicherung**: Speicherung in `pvs`, `pv_sections`, `actions` und `action_suggestions`.
7.  **Webhook**: Das Backend informiert n8n.

## 4. Die Rolle von n8n (Notification Hub)
n8n verarbeitet **keine KI-Daten mehr**. Es ist ein reiner Orchestrator für externe Kommunikation:
*   Empfängt Webhooks vom Backend (`meeting-created`, `transcription-completed`, `daily-reminders`).
*   Holt sich bei Bedarf (sicher autorisiert via `X-Internal-API-Key`) Daten oder PDF-Dateien vom Backend.
*   Versendet E-Mails via SMTP und Erinnerungen via WhatsApp.

## 5. Priorisierte Roadmap (Sicherheit / ISO 27001)
Das System ist stabil. Der nächste Fokus liegt auf der Vorbereitung für die Produktionsumgebung.

**STARTPUNKT FÜR NEUE SESSION:**
Beginne mit "Sofort (Phase 1)" der folgenden ISO 27001 Roadmap:

- [x] **Sofort (Phase 1): Secret Management**. Migration aller Credentials (Datenbank, API-Keys wie OPENAI_API_KEY, MISTRAL_API_KEY) aus der lokalen `.env`-Datei in Kubernetes Secrets (SOPS) oder HashiCorp Vault.
- [x] **Kurzfristig: Netzwerksegmentierung**. Isolierung von Datenbank, Redis und RabbitMQ in ein geschlossenes Subnetz (K8s NetworkPolicies), getrennt vom Frontend/Backend.
- [x] **Parallel: API Gateway & Rate Limiting**. Konfiguration von Cloudflare/AWS WAF oder Traefik vor Nginx zur Abwehr von DDoS und für Rate Limiting.
- [x] **Vor Go-Live**: 
    - SSL/TLS in Transit (HTTPS via Traefik).
    - JWT-Härtung (Token-Laufzeit auf 30 Min reduziert).
    - Erweitertes Session Management (Auto-Timeout nach 15 Min Inaktivität).

## 6. Phase 3: SaaS Transformation & Multi-Tenancy (Abgeschlossen ✅)
Das System wurde erfolgreich von einer Single-Tenant in eine Multi-Tenant SaaS-Plattform transformiert:
- **Daten-Isolation**: Strikte Trennung aller Datensätze (Meetings, Actions, PVs) via `client_id` auf Datenbank- und API-Ebene.
- **Multi-Tenant Auth**: JWT-Payload enthält nun `client_id` und spezifische Rollen (inkl. `system_admin`).
- **Management**: Neues System-Admin Dashboard zur Verwaltung aller Firmen, Status-Steuerung und Umsatz-Monitoring.
- **Provisioning**: Automatisierte Erstellung von Mandanten bei Neuregistrierung.

- [x] **Phase 4: Billing & Onboarding**: 
    - Full Billing infrastructure (Invoices, Usage tracking).
    - High-End SaaS Landing Page (Redesigned with Glassmorphism).
    - System-Admin "God-Mode" Dashboard (Revenue & Tech metrics).
    - Corrected registration flow with company creation.

## 7. Multilingual AI & Dynamic Localization
The system is designed for high-end professional environments where users may switch between Arabic, French, and English.
- **Dynamic Suggestions**: AI Action Suggestions are never "static" in a single language. 
- **User Language Sync**: The backend must detect the user's current dashboard language (provided via API calls) and use Mistral to translate suggestions on-the-fly if they don't match the active UI language.
- **Context Injection**: During PV and Action generation, the backend injects the list of real meeting participants into the AI prompt to ensure precise attribution and avoid name hallucinations (like using the company name instead of a person).

## 8. Bekannte Fixes & Stabilitäts-Hinweise
- **Transcription Pipeline**: Wurde gefixt, um die `client_id` korrekt zu vererben. Celery-Tasks müssen immer die Tenant-ID des Ursprungs-Records nutzen.
- **Minio Buckets**: Bei einem `docker compose down` müssen die Buckets `meeting-recordings` und `meeting-pdfs` ggf. manuell neu erstellt werden (via `mc mb`).
- **Arabic Rendering**: PDFs use native HarfBuzz/Pango support. Manual reshaping (arabic-reshaper) is forbidden as it breaks text extraction (copy-paste).

## 9. Arbeitsregeln für den Agenten
*   Prüfe immer zuerst `docs/PROJECT_STATUS.md`.
*   **Faktenbasiert arbeiten**: Nutze den `codebase_investigator`, um den wahren Zustand des Codes zu verstehen, bevor du Änderungen vorschlägst.
*   **i18n Management**: Übersetzungen existieren redundant in `frontend/src/i18n/locales` (für Vite) und `frontend/public/locales` (für Nginx/Statik). Änderungen müssen immer an BEIDEN Orten erfolgen oder mittels `scripts/sync_locales.sh` synchronisiert werden.
*   **Erst erklären, dann einsetzen**: Erkläre dem Nutzer immer erst den Plan und die technische Begründung, bevor du Dateien modifizierst.
*   Teste Container *lokal* (`docker-compose ps`, `docker logs`), bevor du Code committest.
*   Wenn du Skripte oder Komponenten änderst, verifiziere, dass sie keine Mypy/Flake8/ESLint Fehler in der CI/CD verursachen.
