# AI Session Context - Meeting Automation System

**WICHTIG FÜR DEN KI-AGENTEN**: Lese diese Datei zu Beginn JEDER neuen Session, um den Projektstatus, die Architektur und die nächsten Aufgaben sofort zu verstehen.

## 1. Projektübersicht
Ein mehrsprachiges (Arabisch, Französisch, Englisch) Meeting-Management-System, das Audio aufnimmt, transkribiert, Protokolle (PVs) generiert und Teilnehmer benachrichtigt.

## 2. Technologie-Stack & Architektur
*   **Frontend**: React 18, Vite, TypeScript, MUI, i18next (Fokus auf RTL-Arabisch).
*   **Backend**: FastAPI, Python 3.11, SQLAlchemy 2.0 (`Mapped` Syntax), Pydantic.
*   **Asynchrone Pipeline**: Celery (Worker & Beat) mit RabbitMQ als Broker und Redis als Result-Backend.
*   **Datenbanken**: PostgreSQL (Relationen), MinIO (S3 für Audio/PDF), Redis (Token-Blacklist, Caching).
*   **KI-Dienste**:
    *   **Deepgram Nova-2**: Übernimmt Transkription UND Sprechererkennung (Diarisierung) in einem Aufruf (ersetzt lokales Whisper/Pyannote).
    *   **Mistral AI**: Generiert aus dem Text strukturierte JSON-Protokolle (Zusammenfassung, Entscheidungen, Tasks).
*   **Automatisierung (n8n)**: Fungiert als reiner Notification-Hub. Es verarbeitet keine KI mehr. Es wartet auf Webhooks vom Backend und versendet E-Mails (SMTP) und WhatsApp-Reminders.

## 3. Aktueller Systemstatus (März 2026)
Das System ist nach umfangreichen Fixes **technisch zu 100% stabil und CI/CD-konform (Mypy, Flake8, ESLint)**:
*   **DB-Setup**: `setup-system.sh` ist intelligent und nutzt `alembic stamp head`, falls `Base.metadata.create_all` die Tabellen bereits erstellt hat (keine DuplicateTableErrors mehr).
*   **Celery Async**: Der Event-Loop wird sauber über `asyncio.new_event_loop()` verwaltet, keine `RuntimeError` mehr.
*   **PDF/PV Generierung**: Mistral-Daten werden korrekt und explizit via `db.execute(insert/update)` in die Tabellen `pvs` und `pv_sections` committet, PDFs sind nicht mehr leer.
*   **Frontend i18n**: Hardkodierte Strings in Diagrammen (Recharts) und Tabellen wurden entfernt und vollständig lokalisiert.

## 4. Priorisierte Roadmap (Nächste Aufgaben)
Der Code ist stabil. Der nächste Fokus liegt auf **Infrastruktur-Sicherheit (ISO 27001:2022)** für die Produktionsumgebung.

**STARTPUNKT FÜR NEUE SESSION:**
Beginne mit "Sofort (Phase 1)" der folgenden Roadmap:

- [ ] **Sofort (Phase 1): Secret Management**. Migration aller Credentials (DB, API-Keys wie DEEPGRAM_API_KEY) aus der lokalen `.env`-Datei in Kubernetes Secrets (SOPS) oder HashiCorp Vault.
- [ ] **Kurzfristig: Netzwerksegmentierung**. Isolierung von Datenbank, Redis und RabbitMQ in ein geschlossenes Subnetz (K8s NetworkPolicies), getrennt vom Frontend/Backend.
- [ ] **Parallel: API Gateway & Rate Limiting**. Konfiguration von Traefik/Kong/Cloudflare vor Nginx zur Abwehr von DDoS und für Rate Limiting.
- [ ] **Vor Go-Live**: 
    - Implementierung von Session-Fixation Protection in FastAPI.
    - SSL/TLS für internen Traffic (mTLS).
    - JWT-Härtung (`ACCESS_TOKEN_EXPIRE_MINUTES` auf 30-60 Min reduzieren).

## 5. Arbeitsregeln für den Agenten
*   Prüfe immer zuerst `docs/PROJECT_STATUS.md`.
*   Teste Container *lokal*, bevor du etwas mit `git add/commit` bestätigst.
*   Wenn du Skripte änderst, stelle sicher, dass sie in der CI/CD-Pipeline (`.github/workflows`) weiterhin laufen.