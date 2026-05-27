# Meeting Automation - On-Premise Distribution

## Beschreibung

Meeting-Automation ist eine vollständige On-Premise Lösung für die Automatisierung von Besprechungsmanagement, Transcription und Protokollierung (PV - Protokole Verbal).

### Hauptfunktionen

- **Meeting-Management**: Erstellung und Verwaltung von Besprechungen
- **Audio-Transcription**: Automatische Transkription mittels Gladia AI
- **PV-Generierung**: Automatische Erstellung von Besprechungsprotokollen mit Mistral AI
- **Action-Tracking**: Verfolgung von Aufgaben und Aktionspunkten
- **Multi-Tenant**: Unterstützung für mehrere Mandanten (Clients)
- **n8n Integration**: Workflow-Automatisierung

## Systemanforderungen

### Docker-Installation (empfohlen)
- Docker Engine 20.10+
- Docker Compose v2
- 4GB+ RAM
- 20GB+ Festplattenplatz

### venv-Installation
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- RabbitMQ 3.12+

## Schnellstart

### Option 1: Docker-Installation

1. Archive entpacken:
```bash
tar -xzf meeting-automation-docker.tar.gz
cd meeting-automation-docker
```

2. Installationsskript ausführen:
```bash
chmod +x install.sh
./install.sh
```

3. Services prüfen:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- n8n: http://localhost:5678
- MinIO: http://localhost:9000

4. n8n Workflows importieren:
- Öffne n8n unter http://localhost:5678
- Gehe zu Workflows → Importieren
- Wähle Dateien aus `n8n/workflows/`

### Option 2: venv-Installation (ohne Docker)

1. Archive entpacken:
```bash
tar -xzf meeting-automation-onpremise.tar.gz
cd meeting-automation-onpremise
```

2. Installationsskript ausführen:
```bash
chmod +x install-venv.sh
./install-venv.sh
```

3. Services manuell starten (siehe Ausgabe des Skripts)

## Konfiguration

Die Konfiguration erfolgt über die `.env` Datei. Stellen Sie sicher, dass alle erforderlichen Umgebungsvariablen gesetzt sind:

- `DATABASE_URL` - PostgreSQL Connection String
- `REDIS_URL` - Redis Connection String
- `RABBITMQ_URL` - RabbitMQ Connection String
- `MINIO_*` - MinIO S3 Konfiguration
- `GLADIA_API_KEY` - Gladia API Key (Transcription)
- `MISTRAL_API_KEY` - Mistral API Key (PV-Generierung)

## Services

| Service | Port | Beschreibung |
|---------|------|---------------|
| Frontend | 3000 | React Web UI |
| Backend | 8000 | FastAPI REST API |
| n8n | 5678 | Workflow Automation |
| MinIO | 9000-9001 | S3-kompatibler Storage |
| RabbitMQ | 5672, 15672 | Message Queue |
| Redis | 6379 | Cache |

## Sicherheit

- Alle Dienste sollten hinter einem Reverse Proxy (z.B. Nginx) betrieben werden
- SSL/TLS Zertifikate konfigurieren
- Firewall-Regeln für externe Zugriffe einrichten
- Regelmäßige Backups der PostgreSQL-Datenbank durchführen

## Troubleshooting

### Container startet nicht
```bash
docker-compose logs -f
```

### Datenbank-Migration fehlschlägt
```bash
docker-compose exec backend alembic upgrade head --verbose
```

### Frontend lädt nicht
```bash
docker-compose logs frontend
```

### Alle Services neu starten
```bash
docker-compose restart
```

## Lizenz

Proprietär - Alle Rechte vorbehalten