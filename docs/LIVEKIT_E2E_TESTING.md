# LiveKit Integration — E2E Test Strategie

**Erstellt:** 2026-06-05 | **Status:** Produktionsreif ✅

---

## Übersicht

**7/7 E2E Tests bestanden** — LiveKit, Egress und Webhook-Integration funktionieren vollständig im Docker-Compose-Stack.

## Test-Suite (Letzter Stand: 2026-06-05)

| # | Test | Endpoint | Erwartet | Beschreibung |
|---|------|----------|----------|-------------|
| 1 | `test_livekit_token_endpoint` | POST `/meetings/{id}/livekit/token` | 200 + JWT | Authentifizierter User bekommt LiveKit Token |
| 2 | `test_livekit_start_recording` | POST `/meetings/{id}/livekit/start-recording` | 201 | Egress Recording wird gestartet, egress_id + recording_id zurück |
| 3 | `test_livekit_webhook_egress_completed` | POST `/livekit/webhooks` | 200 + ok=True | Webhook mit gültigem INTERNAL_API_SECRET |
| 4 | `test_livekit_webhook_unauthorized` | POST `/livekit/webhooks` | 403 | Webhook mit falschem Secret |
| 5 | `test_livekit_webhook_unknown_event` | POST `/livekit/webhooks` | 200 + event name | Unbekannte Events werden akzeptiert |
| 6 | `test_livekit_meeting_creates_room` | POST `/meetings/` | 200/201 | Meeting-Erstellung triggert LiveKit Room (non-fatal) |
| 7 | `test_livekit_token_response_structure` | POST `/meetings/{id}/livekit/token` | 200 + JWT + ws:// | Token ist gültiger JWT, server_url ist ws:// |

## Ergebnisse

```bash
# 7/7 bestanden in 5.81 Sekunden
pytest tests/e2e/test_livekit_integration.py -v --tb=short
```

## Egress-Integration (Neu: Produktionsreif)

- **Egress Worker:** `livekit/egress:latest` Container läuft gesund
- **Redis-PSRPC:** Server ↔ Egress über Redis synchronisiert
- **Egress-Konfig:** `room_composite_cpu_cost` angepasst für 2-CPU-Host
- **MinIO/S3:** Recordings werden als Composite-File exportiert
- **Webhook:** `egress.completed` triggert ISO 27001 Audit Trail

## Test-Konfiguration

```bash
# E2E Tests gegen Docker-Container (LiveKit + Egress aktiv)
E2E_BASE_URL="http://localhost:8000" pytest tests/e2e/test_livekit_integration.py -v

# Mit LiveKit Server + Egress Worker: start-recording → 201 (Recording Active)
# Ohne Egress Worker: → 503 (Service Unavailable)
```

## Architektur

```
Frontend (React + LiveKit SDK) ──WebSocket──→ LiveKit Server (7880)
                                                    │
Test Client (venv_test) ──HTTP──→ Backend API (8000)  │
                                         │              │
                                         ├── PostgreSQL ←── Redis PSRPC
                                         ├── MinIO/S3 ←── Egress Worker
                                         └── RabbitMQ (Celery Pipeline)
```

## Implementierte Dateien

| Datei | Typ | Beschreibung |
|-------|-----|-------------|
| `docker-compose.yml` | Config | livekit-server + livekit-egress Container |
| `livekit.yaml` | Config | LiveKit Server Config (Redis, Keys, Debug) |
| `livekit-egress.yaml` | Config | Egress Worker Config (S3/MinIO, CPU-Cost) |
| `backend/app/services/livekit_service.py` | Service | Room/Token/Egress API (LiveKitAPI) |
| `backend/app/api/v1/livekit.py` | API | 3 Endpunkte (Token, Recording, Webhook) |
| `backend/app/services/meeting_service.py` | Anpassung | LiveKit Room bei Meeting-Erstellung und Löschung |
| `frontend/src/components/meetings/MeetingRoom.tsx` | Frontend | LiveKit Room + ControlBar + ParticipantsList |
| `backend/requirements.txt` | Deps | livekit-api >= 1.0.0 |
| `backend/requirements-dev.txt` | Deps | livekit-api >= 1.0.0 |
| `tests/e2e/test_livekit_integration.py` | Tests | 7 E2E Tests (5.81s) |

## Nächste Schritte

1. ✅ `docker compose up -d livekit-server` — LiveKit Server starten
2. ✅ Alle 7 Tests → 200/201 (start-recording funktioniert)
3. 🔄 **Frontend:** Professionelle intelligente UI implementieren (MeetingRoom.tsx Refaktorisierung)
4. 🔄 **E2E-Test:** Full-Stack E2E-Test mit Browser (Playwright/Selenium)
5. 🔄 **Celery-Pipeline:** Egress-Webhook → Audio-Transcription → PV-Generierung (ASR Pipeline)
