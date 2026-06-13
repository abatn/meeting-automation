# SKILL: Meeting Automation Pipeline — Wissensbasis

**Version:** 2026-06-13
**Status:** Aktuell
**Ziel:** Professionelles Verständnis der Pipeline für fundierte Entscheidungen

---

## 1. Pipeline-Architektur

### Flow (LiveKit → PV)
```
Meeting erstellen → LiveKit Room → Egress Recording → MinIO Upload
    → Webhook (egress_ended) → Redis SETNX Dedup → Celery Task
    → S3 Download → Gladia Transcription (3-Step)
    → Speaker Identification (ONNX + Heuristic + Regex + Mistral Fusion)
    → Display Transcript "Speaker 0" → "Abdelkader Batnini"
    → Sentinel MAP → Mistral PV REDUCE (Temperature 0.1)
    → Assignee Resolution (5-step)
    → Auto-Enrollment → DB Save + Audit + n8n Webhook
```

### Timeline (testbobo: 14s)
```
0:00  Recording start
0:02  S3 Download + Gladia Upload (2s)
0:08  Gladia Transcription complete (6s)
0:15  Speaker ID (7s, heuristic)
0:20  Mistral PV API Call (2s)
0:22  Actions zugewiesen + Recording complete
```

---

## 2. Modul-Map (30 Services)

### Pipeline
| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `transcription_tasks.py` | 1116 | Celery Task: Orchestrator |
| `gladia_service.py` | 136 | 3-Step API (Upload/Request/Polling) |
| `sentinel_service.py` | 76 | Lokale SLM (MAP summarization) |
| `pv_service.py` | 354 | Dual-Context (Summary + Transcript) |
| `mistral_fusion_service.py` | 302 | Speaker-ID LLM-Fusion |

### Speaker Identification
| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `speaker_embedding_service.py` | 253 | ONNX 192-dim Embeddings |
| `speaker_profile_service.py` | 249 | DB CRUD + Cosine Distance |
| `assignee_resolver.py` | 370 | 5-step Resolution |
| `phonetic_matcher.py` | 300 | Double Metaphone |
| `auto_enrollment_service.py` | 207 | Auto-Enrollment |

### Storage & Audio
| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `recording_service.py` | 277 | S3 Upload + Pipeline Trigger |
| `audio_segment_service.py` | 244 | ffmpeg Segment Extraction |

### Tasks
| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `celery_app.py` | 47 | Celery Config |
| `email_tasks.py` | 176 | Email Tasks |
| `feedback_tasks.py` | 95 | Feedback Resolution |

---

## 3. Infrastructure

### PostgreSQL
- 15 Tabellen mit Multi-Tenancy (client_id auf ALLEN Kern-Tabellen)
- Fernet Encryption auf PV/Transcription Spalten
- 24 fehlende Indexe identifiziert, 15 hinzugefügt

### Redis
- 3 Zwecke: (1) Celery Result Backend, (2) Token Blacklist, (3) WebSocket Pub/Sub
- Connection Pool: max_connections=10

### RabbitMQ
- 3 Queues: transcription, email, maintenance
- Healthcheck: rabbitmq-diagnostics
- Ports: 5672 (AMQP), 15672 (Management)

### MinIO
- S3-kompatibel
- Buckets: meeting-recordings, meeting-pdfs
- Client-ID Prefix für Multi-Tenancy

### LiveKit
- SFU für Echtzeit-Audio
- Egress für Recording → MinIO
- Webhook: egress_ended → Celery Pipeline
- Ports: 7880 (Signaling), 7881 (TCP Fallback), 7881-7890 (UDP)

### n8n
- Reiner Notification Hub (keine KI mehr)
- 7 Workflows: meeting-created, audio-uploaded, transcription-completed, daily-reminders, user-invited, meeting-status-changed, pv-validated
- Authentication: X-Internal-API-Key

---

## 4. Bekannte Bugs

| Bug | Datei | Fix |
|-----|-------|-----|
| Speaker Heuristic: erster Teilnehmer | `transcription_tasks.py:374` | `len(all_speaker_groups) == 1` |
| Feedback asyncpg Loop | `feedback_tasks.py:83` | asyncpg pro Task |
| ONNX Singleton nicht init | `speaker_embedding_service.py:247` | Lazy Init |
| `_run_async` broken | `transcription_tasks.py:44` | Revert zu `get_event_loop()` |
| Duplicate Actions bei Feedback | Frontend | Debounce |

---

## 5. Test Strategy

- **E2E**: `docker-compose.e2e.yml` + `E2E_TEST=true`
- **Core**: 89/89 Tests
- **Smoke**: `pytest tests/e2e/test_smoke.py -v`
- **Gesamt**: 349/354 (98.6%)

---

## 6. Security (ISO 27001)

- Multi-Tenancy: client_id auf ALLEN Queries
- Audit: audit_service.log_action() für ALLE Änderungen
- Encryption: Fernet auf PV/Transcription Spalten
- JWT: httpOnly Cookies + X-Client-ID Validation
- Session: Auto-Logout nach 15 Min Inaktivität

---

## 7. Performance

- **Target**: ≤90s Pipeline
- **Current**: ~14s (testbobo)
- **Optimierungen**: Gladia Adaptive, Redis Pool, Profile Loading, Parallel ffmpeg

---

## 8. Deployment

- **Docker**: docker-compose.yml (12 Services)
- **Kubernetes**: PRODUCTION_DEPLOYMENT_PLAN.md
- **E2E**: docker-compose.e2e.yml (isolierte Ports)
