# PROTOKOLL: PART 39 - ADVANCED MONITORING (PHASE 5)

**Datum:** 22.03.2026
**Status:** Abgeschlossen ✅
**Ziel:** Einführung eines erweiterten Monitorings und System-Telemetrie für das Technik-Dashboard im Rahmen von Phase 5 (Production Operations & Global Optimization).

## 🎯 ZIEL

Die `Mission Control` (Technik-Dashboard) sollte tiefgehende, verlässliche System-Metriken direkt aus den Services extrahieren können, anstatt nur einfache Pings abzusetzen.

## 🔧 TECHNOLOGIEN
- Docker Python SDK
- PostgreSQL Views (`pg_stat_activity`, `pg_stat_database`)
- Redis INFO (Memory, Stats)
- Boto3 (MinIO)
- RabbitMQ HTTP API
- Recharts (React)

## 📝 DURCHGEFÜHRTE ARBEITSSCHRITTE

### 1. Backend: Architektur-Änderungen (`monitoring_service.py`)
- Ein dedizierter `MonitoringService` wurde in `app/services/monitoring_service.py` erstellt, um asynchrone Health Checks und Metriken zu zentralisieren.
- Die API-Route in `app/api/v1/admin.py` wurde überarbeitet, um `asyncio.gather` für die parallele Abfrage der neuen Metriken zu verwenden, anstatt dies sequenziell im Controller zu erledigen.

### 2. Metrik-Implementierungen
- **Container-Telemetrie**: Das `docker` Python-Paket wurde installiert (`requirements.txt`), und der Socket `/var/run/docker.sock` wurde im `docker-compose.yml` an den Backend-Container durchgereicht, damit es CPU, RAM und Uptime-Metriken für sich, das Frontend und Celery in Echtzeit ermitteln kann.
- **PostgreSQL**: Verwendung der internen PostgreSQL-Views `pg_stat_activity` (für die Anzahl aktiver Verbindungen und langsame Queries über 100ms) und `pg_stat_database` (für die Cache Hit Ratio).
- **Redis**: Erweiterung der Info-Abfrage um `memory` (Speicherbelegung in MB) und `stats` (Hit Ratio, Evicted Keys).
- **Storage / MinIO**: Nutzung von `boto3` paginator `list_objects_v2`, um alle Objekte zu zählen und die tatsächliche Speicherbelegung präzise in Megabytes umzurechnen.
- **RabbitMQ**: Auslesen von "Messages" und "Unacknowledged Messages" über die HTTP API sowie Speicherung rudimentärer Trend-Daten (letzte Stunde) im Redis Cache.
- **KI Services**: Einführung von Tracing (Latenz-Messung) in den AI-Calls von `pv_service.py` (Mistral) und `gladia_service.py` (Gladia). Die Call-Dauer, Erfolge und Fehler werden in Redis-Listen gespeichert, um den Durchschnitt und die Fehlerquote pro Service im Dashboard anzuzeigen.

### 3. Frontend-Visualisierung (`TechnikDashboard.tsx`)
- Vollständige Umstrukturierung der UI mithilfe von Material UI Cards und Paper-Komponenten.
- **Container Telemetry UI**: Neue Darstellung der CPU- und RAM-Nutzung pro Service (Backend, Frontend, Celery).
- **RabbitMQ Trend-Graphen**: Einbindung von `Recharts` zur Darstellung eines `BarCharts` für aktive und unacknowledged Messages pro RabbitMQ-Queue.
- **AI Latency Monitoring**: Detaillierte Darstellung der durchschnittlichen Response-Zeit (in Sekunden) und der Fehlerquote für Mistral und Gladia.

## ⚠️ HERAUSFORDERUNGEN & LÖSUNGEN
- **Docker Python SDK Bug**: Eine bekannte Inkompatibilität des Python Docker SDKs mit `urllib3>=2` bei der Verwendung von Sockets (Fehler: `URLSchemeUnknown: Not supported URL scheme http+docker`) wurde behoben. Wir aktualisierten das Docker-Paket auf die neuste Version (`docker>=7.1.0`), die vollen Support für `urllib3` v2 mitbringt. 
- **Vite Build Memory Crash (Bus Error)**: Beim Frontend-Build kam es zu `Bus error (core dumped)` aufgrund extremer RAM-Auslastung durch `esbuild` unter Alpine Linux. 
  - **Lösung**: Umstellung der `builder`-Stage im `frontend/Dockerfile` von `node:20-alpine` auf Debian-basiertes `node:20`. Hinzufügen von `ENV NODE_OPTIONS="--max-old-space-size=4096"` sowie einer Windows `.wslconfig` (6GB RAM, 8GB Swap) zur Systemstabilisierung.
- **Feature Shells & Dummy-Daten im Dashboard**: Die Dashboards (`DashboardParticipant.tsx`, `AnalyticalReports.tsx`, `ActionTracker.tsx`) zeigten bisher statische Demo-Daten ("Action 1", "Sami Ben Ali"). 
  - **Lösung**: Vollständige Anbindung an Backend-Endpoints (`/reports/dashboard/participant`, `/actions/my-actions`), Implementierung von echten SQL-Queries im `ReportService` (inkl. Multi-Tenant Filterung) und Hinzufügen der dynamischen Liste "Recent Meetings" im Planer.
- **Aggressive UI-Farben**: Zu viele Elemente nutzten die Signalfarbe Rot (`error`), was unprofessionell wirkte.
  - **Lösung**: Umstellung der `secondary` Palette im Theme auf ein professionelles Schiefergrau (`#475569`) und logische Status-Badges (z.B. PENDING = warning, DISABLED = default).
- **Action Tracker Unsichtbarkeit (AI Zuweisungen)**: Akzeptierte KI-Aufgaben tauchten im Tracker nicht auf, da die SQL-Abfrage strikt nach `user_id` des eingeloggten Nutzers suchte. Die KI weist Aufgaben aber externen Namen ("Amal", "Sami") zu, die keine IDs haben. Zusätzlich blieben erledigte Aufgaben für immer in der Tracker-Liste sichtbar.
  - **Lösung**: Der Tracker-Endpunkt `/my-actions` lädt nun alle Mandanten-Aufgaben (`client_id`). Im Frontend (`ActionTracker.tsx`) wurde ein Filter ergänzt, der erledigte Aufgaben ("Completed") live ausblendet, um die To-Do-Liste sauber zu halten.
- **Team Productivity Statistik (Ghost Users)**: Im Analytik-Dashboard wurden nur erledigte Aufgaben registrierter Nutzer (z.B. Abdelkader) gezählt, Aufgaben von KI-identifizierten Teilnehmern fielen aus der SQL-Gruppierung.
  - **Lösung**: Umbau der `get_team_productivity` SQL-Query. Nutzung von `COALESCE(UserModel.full_name, Assignment.external_name)`, um registrierte Nutzer und externe KI-Teilnehmer gleichwertig zu aggregieren und im Report anzuzeigen.
- **Frontend Docker Build Cache (Phantom Bugs)**: Code-Änderungen an den React-Komponenten kamen im Browser nicht an, da Docker die alten JS-Bundles aus dem Cache wiederverwendete.
  - **Lösung**: Forcierter Rebuild mittels `docker compose build --no-cache frontend` und `--force-recreate` zur endgültigen Vernichtung der veralteten JavaScript-Dateien.
- **Meeting Planner: Dynamische Teilnehmer & Gäste**: Die Liste der Teilnehmer im Meeting-Planer war bisher hartkodiert.
  - **Lösung**: Einführung einer dynamischen `Autocomplete`-Komponente in `MeetingPlanner.tsx`. Es werden nun alle aktiven, registrierten Nutzer des aktuellen Mandanten aus der Datenbank geladen. Zusätzlich können per Tastendruck ("Enter") externe E-Mail-Adressen für Gäste frei eingetippt und hinzugefügt werden.
- **Meeting Planner: Statische Uhrzeit**: Meetings wurden im Backend hart auf 10:00 Uhr (UTC) terminiert, das UI fragte nur das Datum ab.
  - **Lösung**: Hinzufügen eines dynamischen Time-Pickers neben dem Datum. Die Startzeit und die berechnete Endzeit (+1 Stunde) werden nun exakt an das Backend übermittelt.
- **E-Mail-Einladungen via n8n (Payload Bug)**: Externe Gäste erhielten keine Einladungen, da der n8n-Webhook (`meeting-created`) fehlerhaft die `user_id` anstelle der tatsächlichen `email` übertrug.
  - **Lösung**: Korrektur in `meeting_service.py` (`_trigger_n8n_meeting_created`), sodass nun explizit `p.email` und `p.name` für jeden Teilnehmer (ob registriert oder Gast) an das Automatisierungs-Tool gesendet werden.
- **Professionelles Team Management (Mitarbeiter-Verzeichnis)**: Teilnehmer mussten bisher manuell per E-Mail im Meeting-Planer eingetippt werden, was unprofessionell und fehleranfällig war.
  - **Lösung**: Implementierung eines zentralen Team-Managements. Einführung der Tabelle `team_members`, einer neuen Management-Seite im Frontend und einer intelligenten Suche im Meeting-Planer, die sowohl registrierte Nutzer als auch gespeicherte Team-Mitglieder vorschlägt.
- **Audit-Log Absturz (TypeError)**: Beim Anlegen/Löschen von Team-Mitgliedern kam es zu einem "Internal Server Error", da der `AuditService` mit dem falschen Keyword `details` statt `new_values` aufgerufen wurde.
  - **Lösung**: Korrektur aller `log_action` Aufrufe im `TeamService`, um die ISO 27001 Konformität ohne Systemabstürze zu gewährleisten.
- **Word-Download (DOCX) Crash**: Der Export schlug mit einem 500-Fehler fehl, wenn die Mistral-KI überlastet war oder Lokalisierungs-Keys durch Code-Fehler überschrieben wurden.
  - **Lösung**: Saubere Zusammenführung der `LOCALES` Datenstruktur in `docx_service.py` zur Vermeidung von `KeyErrors`. Implementierung einer "Sicherheits-Leine": Schlägt die KI-Übersetzung fehl (z.B. HTTP 503), wird das Dokument nun automatisch in der Originalsprache generiert, anstatt den Download abzubrechen.

## 📊 ERGEBNIS
Das System-Dashboard liefert nun hochauflösende Einblicke in die gesamte Architektur und ermöglicht dem Betreiber sofortiges Eingreifen bei Latenzen oder Speicher-Engpässen. Gleichzeitig sind die Benutzer-Dashboards nun vollständig mit echten, mandantenfähigen Datenbank-Metriken synchronisiert und frei von Dummy-Daten. Damit ist der erste Meilenstein von Phase 5 vollständig abgeschlossen.
