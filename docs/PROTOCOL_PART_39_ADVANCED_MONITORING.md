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

## 📊 ERGEBNIS
Das System-Dashboard liefert nun hochauflösende Einblicke in die gesamte Architektur und ermöglicht dem Betreiber sofortiges Eingreifen bei Latenzen oder Speicher-Engpässen. Gleichzeitig sind die Benutzer-Dashboards nun vollständig mit echten, mandantenfähigen Datenbank-Metriken synchronisiert und frei von Dummy-Daten. Damit ist der erste Meilenstein von Phase 5 vollständig abgeschlossen.
