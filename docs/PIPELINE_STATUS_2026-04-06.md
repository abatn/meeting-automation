# Pipeline Status — 2026-04-06

## Umgebung
- **Host**: OCI VM, aarch64 (ARM64), IP: `158.180.18.110`
- **Branch**: `fix/p1-critical-issues-20260405`
- **Stack**: Docker Compose (DEV)

---

## Gesamtstatus

| Komponente | Status | Anmerkung |
|---|---|---|
| Backend (FastAPI) | ✅ Healthy | Port 8000 |
| Frontend (nginx) | ✅ Running | Port 3000 |
| PostgreSQL | ✅ Healthy | Port 5432 |
| Redis | ✅ Healthy | Port 6379 |
| RabbitMQ | ✅ Healthy | Port 5672 |
| MinIO | ✅ Healthy | Port 9000 |
| Celery Worker | ✅ Running | |
| Celery Beat | ✅ Running | |
| n8n | ✅ Running | Port 5678 |
| OnlyOffice | ✅ Running | Port 8081 — ARM64-Fix angewendet |

---

## Pipeline-Schritte: Validierungsstatus

| Schritt | Endpoint | Status | Beweis |
|---|---|---|---|
| 1. Login | `POST /api/v1/auth/login` | ✅ | JWT Token ausgestellt |
| 2. Team Member einladen | `POST /api/v1/team` | ✅ | User PENDING + ActivationToken |
| 3. Meeting erstellen | `POST /api/v1/meetings` | ✅ | n8n webhook → 404 (Workflow nicht importiert) |
| 4. Meeting starten | `POST /api/v1/meetings/{id}/start` | ✅ | Status → in_progress |
| 5. Aufnahme starten | `POST /api/v1/recordings/stream/start` | ✅ | |
| 6. Aufnahme stoppen | `POST /api/v1/recordings/stream/stop` | ✅ | MinIO Upload → Celery Task ausgelöst |
| 7. Celery: Transkription | Gladia → Mistral | ✅ | PV + Actions + Assignments in DB |
| 7a. Fuzzy-Matching | `ILIKE '%{name}%'` | ✅ | action_assignments korrekt befüllt |
| 7b. n8n transcription-completed | `POST http://n8n:5678/webhook/...` | ❌ | 404 — Workflow nicht in n8n importiert |
| 8. PV abrufen | `GET /api/v1/pv/meeting/{id}` | ✅ | PV vorhanden |
| 9. OnlyOffice Config | `GET /api/v1/pv/{id}/onlyoffice/config` | ✅ | DOCX generiert, S3 Upload OK |
| 10. OnlyOffice Editor | Browser lädt JS von `:8081` | ✅ | 200 OK nach ARM64-Fix |
| 11. Callback | `POST /api/v1/pv/{id}/onlyoffice/callback` | 🔄 Offen | Test ausstehend |
| 12. PDF Download | `GET /api/v1/pv/{id}/download` | 🔄 Offen | Test ausstehend |

---

## Behobene Probleme heute

### P1: Accept-Button → 500 Error
- **Ursache**: `status="pending"` (lowercase) in `action_service.py:377`
- **Fix**: `status="PENDING"` — PostgreSQL Enum erwartet uppercase
- **Datei**: `backend/app/services/action_service.py:377`

### P2: OnlyOffice startet nicht (ARM64)
- **Ursache**: `onlyoffice/documentserver:latest` (x86) — internes RabbitMQ startet nicht auf aarch64
- **Fix**: Image → `latest-arm64` + `AMQP_URI` auf externes RabbitMQ
- **Datei**: `docker-compose.yml`

### P3: OnlyOffice nginx Redirect auf `http://onlyoffice/...`
- **Ursache**: Container-Hostname wurde für absolute Redirects verwendet
- **Fix**: `hostname: "${HOST_IP:-localhost}"` + `SERVER_NAME=${HOST_IP:-localhost}`
- **Datei**: `docker-compose.yml`

### P4: Port 8081 extern nicht erreichbar
- **Ursache**: OCI Security Group fehlte Ingress Rule
- **Fix**: Port 8081/tcp in OCI Console freigegeben

### P5: Dynamische Host-Konfiguration
- **Ursache**: IP-Adressen waren hardcodiert
- **Fix**: `HOST_IP` in `.env` — alle URLs in `docker-compose.yml` abgeleitet

---

## Offene Punkte

| # | Problem | Priorität | Aktion |
|---|---|---|---|
| 1 | n8n Workflows nicht importiert | P1 | Alle 5 JSONs aus `n8n/workflows/` in `http://158.180.18.110:5678` importieren & aktivieren |
| 2 | n8n Webhook-URLs in `.env` falsch | P1 | `/webhook/2/webhook/...` → `/webhook/...` korrigieren |
| 3 | OnlyOffice Callback → PDF Test | P2 | Edit Online → Speichern → PDF Download testen |
| 4 | Phase 2 Commit ausstehend | P2 | `team_service.py` + Migration `c6d7e8f9a0b1` committen |
| 5 | CORS_ORIGINS enthält keine VM-IP | P3 | Bei CORS-Fehlern: `158.180.18.110:3000` ergänzen |

---

## Nächste Schritte

```bash
# 1. n8n Workflows importieren
open http://158.180.18.110:5678
# → Settings → Import → alle Dateien aus n8n/workflows/ hochladen → aktivieren

# 2. n8n Webhook-URLs fixen (.env)
N8N_WEBHOOK_MEETING_CREATED=http://n8n:5678/webhook/meeting-created
N8N_WEBHOOK_TRANSCRIPTION_COMPLETED=http://n8n:5678/webhook/transcription-completed
N8N_WEBHOOK_DAILY_REMINDER=http://n8n:5678/webhook/daily-reminders

# 3. Backend neu starten
docker compose up -d backend

# 4. Phase 2 committen
git add backend/app/services/team_service.py
git add backend/alembic/versions/c6d7e8f9a0b1_*.py
git commit -m "fix(team): secure PENDING passwords and enforce email uniqueness per client"
```
