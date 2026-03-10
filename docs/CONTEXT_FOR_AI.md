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
Die Pipeline wurde auf maximale Zuverlässigkeit getrimmt. **(Deepgram wird NICHT verwendet)**.
1.  **Audio-Upload**: Frontend streamt Audio-Chunks in Echtzeit zu MinIO.
2.  **Celery-Trigger**: Nach Abschluss der Aufnahme startet die asynchrone Task `process_recording`.
3.  **Download**: Der Worker lädt die Gesamtdatei aus MinIO.
4.  **Diarization**: Der `DiarizationService` (lokales Pyannote) erstellt Sprecher-Segmente (aktuell aus Ressourcengründen ggf. übersprungen, Fallback-Logik vorhanden).
5.  **Transkription**: `transcription_service.py` sendet das Audio an **OpenAI Whisper (`whisper-1`)** mit `response_format="verbose_json"`, um hochpräzise Texte inklusive Wort-Zeitstempeln zu erhalten.
6.  **Zusammenführung**: `match_timestamps` verheiratet den Whisper-Text mit den Sprecher-Segmenten.
7.  **PV-Generierung**: Der formatierte Text geht an den **Mistral AI (`mistral-large-latest`)** Service. Mistral liefert ein striktes JSON mit `summary`, `decisions` und `actions`.
8.  **Datenbank-Speicherung**: Die Ergebnisse werden explizit und sicher via `db.execute(insert/update)` in die Tabellen `pvs`, `pv_sections` (wichtig für die PDF-Generierung!) und `actions` gespeichert.
9.  **Webhook**: Das Backend informiert n8n.

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
- [ ] **Vor Go-Live**: 
    - SSL/TLS in Transit (auch intern via mTLS).
    - JWT-Härtung (`ACCESS_TOKEN_EXPIRE_MINUTES` auf 30-60 Min reduzieren).
    - Erweitertes Session Management (Fixation Protection, Auto-Timeout).

## 6. Arbeitsregeln für den Agenten
*   Prüfe immer zuerst `docs/PROJECT_STATUS.md`.
*   **Faktenbasiert arbeiten**: Nutze den `codebase_investigator`, um den wahren Zustand des Codes zu verstehen, bevor du Änderungen vorschlägst.
*   Teste Container *lokal* (`docker-compose ps`, `docker logs`), bevor du Code committest.
*   Wenn du Skripte oder Komponenten änderst, verifiziere, dass sie keine Mypy/Flake8/ESLint Fehler in der CI/CD verursachen.
