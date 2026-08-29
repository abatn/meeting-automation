# SKILL: Meeting Pipeline — Code-basierte Wissensbasis

**Erstellt:** 2026-06-14 | **Quelle:** Nur aktueller Code (keine Pläne, keine alten Doku)

---

## 1. Pipeline-Architektur (Ist-Zustand)

### Flow
```
LiveKit Egress → MinIO/S3 → Celery Task "process_recording"
  → S3 Download (_download_audio, Zeile 751)
  → Gladia V2 3-Step (transcribe_and_diarize, Zeile 175)
  → Speaker Identification (_identify_speakers, Zeile 381)
    → Heuristic (_match_speaker_to_participant, Zeile 299)
    → ONNX Embedding (speaker_embedding_service, Zeile 179)
    → Regex Self-Introduction (detect_self_introduction, Zeile 480)
    → Mistral Fusion (mistral_fusion_service, Zeile 492)
  → Display Transcript: "Speaker 0" → "Name" (Zeile 200-213)
  → Sentinel MAP (sentinel.summarize_chunk, Zeile 222-225)
  → Mistral PV REDUCE (PVService.generate_pv, Zeile 230-237)
  → Assignee Resolution (AssigneeResolver, Zeile 882-886)
  → Auto-Enrollment (enrollment_service, Zeile 557-577)
  → DB Save + Audit + n8n Webhook (Zeile 240-264)
```

### Celery Task Definition
- **Datei:** `backend/app/tasks/transcription_tasks.py:1102-1112`
- **Task-Name:** `process_recording`
- **Retry:** `autoretry_for=(Exception,)`, `max_retries=3`, `retry_backoff_max=600`
- **Entry:** `_run_async(_process_recording_pipeline(recording_id, client_id))` (Zeile 1112)

### Pipeline Status-Tracking
- **Redis Pub/Sub:** `publish_status()` (Zeile 70-77)
- **Channel:** `transcription_status_{recording_id}`
- **States:** `uploaded` → `transcribing` → `analyzing` → `completed` | `failed`

---

## 2. Module (nur Code-Quellen)

### Pipeline-Orchestrierung
| Datei | Zeilen | Funktion |
|-------|--------|----------|
| `backend/app/tasks/transcription_tasks.py` | 1116 | `_process_recording_pipeline()` (Zeile 139), `_identify_speakers()` (Zeile 381), `_save_pv_and_actions()` (Zeile 834) |

### Transkription
| Datei | Zeilen | Funktion |
|-------|--------|----------|
| `backend/app/services/gladia_service.py` | 149 | `transcribe_and_diarize()` — 3-Step: Upload → Request → Polling (Zeile 28) |
| `backend/app/services/sentinel_service.py` | 76 | `summarize_chunk()` — Qwen-1.5B lokales SLM (Zeile 41) |

### Speaker Identification
| Datei | Zeilen | Funktion |
|-------|--------|----------|
| `backend/app/services/speaker_embedding_service.py` | 261 | ONNX 192-dim ECAPA-TDNN Embeddings (Zeile 23) |
| `backend/app/services/speaker_profile_service.py` | 249 | DB CRUD + Cosine Distance Matching |
| `backend/app/services/speaker_name_detector.py` | 107 | Regex Self-Introduction Patterns (EN/AR/FR/DE) (Zeile 8-24) |
| `backend/app/services/mistral_fusion_service.py` | 302 | LLM-basierte Speaker-Fusion (Zeile 25) |
| `backend/app/services/auto_enrollment_service.py` | 207 | Auto-Enrollment nach Identifikation (Zeile 15) |

### PV-Generierung
| Datei | Zeilen | Funktion |
|-------|--------|----------|
| `backend/app/services/pv_service.py` | 354 | `generate_pv()` Dual-Context (Zeile 56), `translate_content()` (Zeile 254) |

### Assignee Resolution
| Datei | Zeilen | Funktion |
|-------|--------|----------|
| `backend/app/services/assignee_resolver.py` | 370 | 5-step: Speaker Mapping → Participant → Phonetisch → Fuzzy → External (Zeile 119-179) |
| `backend/app/services/phonetic_matcher.py` | 362 | Double Metaphone (Zeile 16) |

### Frontend
| Datei | Zeilen | Funktion |
|-------|--------|----------|
| `frontend/src/components/meetings/MeetingRoom.tsx` | 1820 | LiveKit Room + Recording Controls + Transcription Polling + AI Insights |

---

## 3. Speaker Identification Pipeline (Detail)

### 5-Signal-Aggregation (`_identify_speakers`, Zeile 381-643)

| Signal | Quelle | Score | Zeile |
|--------|--------|-------|-------|
| Heuristic | `_match_speaker_to_participant()` | 0.75 | 444-456 |
| ONNX Audio | `profile_service.match_speaker_from_list()` | 0.30-0.90 | 458-476 |
| Regex Text | `detect_self_introduction()` | 0.85 | 478-485 |
| Mistral LLM | `mistral_fusion_service.fuse_speaker_mapping()` | variabel | 487-503 |

### Aggregation (Zeile 505-542)
- Gewichtete Konsensus über alle Signals
- Multi-Source-Bonus: `+15% pro zusätzlichem Source` (Zeile 528-529)
- Conflict-Penalty: `confidence *= max(1.0 - conflict_ratio * 0.5, 0.3)` (Zeile 532-535)
- **Validierung:** Name MUSS in candidates sein (Zeile 544-552)

### Heuristic-Logik (`_match_speaker_to_participant`, Zeile 299-378)
1. Single Participant → return participant (Zeile 322-323)
2. Main Speaker = Creator Heuristic (Zeile 326-353)
3. Text Reference Matching: "wie X", "danke X" (Zeile 355-371)
4. Order Heuristic: Speaker 0 → first participant (Zeile 373-376)

### Parallel Processing (Zeile 619-642)
- Batch-Größe: 3 Speaker parallel
- `asyncio.gather()` pro Batch
- 0.1s Delay zwischen Batches

---

## 4. PV-Generierung (Detail)

### Dual-Context Approach (`pv_service.py:56-252`)
- **Sentinel Summary:** Kompakt, für PV-Übersicht (Zeile 68-69)
- **Full Transcript (Display):** Für Action-Assignment, "wer was gesagt hat" (Zeile 69-70)

### Mistral Prompt (Zeile 138-180)
- **Model:** `mistral-large-latest` (Zeile 187)
- **Temperature:** 0.1 (Zeile 197) — deterministisch
- **Timeout:** 60s (Zeile 205)
- **Anti-Hallucination:** Closed List für Assignees (Zeile 150-155)
- **Response Format:** `json_object` (Zeile 196)

### Validation (Zeile 226-237)
- Assignees gegen Closed List geprüft
- Invalid Assignees geloggt
- Schema-Validierung: `_validate_pv_schema()` (Zeile 18-32)

---

## 5. Frontend Integration (MeetingRoom.tsx)

### LiveKit (Zeile 61-63, 965-1001)
- `LiveKitRoom` mit `token`, `serverUrl`, `connect={true}`, `audio={true}`, `video={false}`
- Bridge-Komponenten: `LiveKitConnectionBridge`, `LiveKitDisconnectBridge`, `MicToggleBridge`

### Recording Controls (Zeile 709-751)
- `handleStartRecording()` → `meetingsApi.startRecording()` (Zeile 714)
- `handleStopRecording()` → `meetingsApi.stopRecording()` (Zeile 730)
- `handlePauseRecording()` — nur lokaler State (LiveKit Egress hat kein native Pause) (Zeile 741-746)

### Polling (Zeile 594-701)
- Transkription: alle 5s (`pollTranscriptionData`, Zeile 592)
- AI Insights: alle 8s (`pollAIInsights`, Zeile 694)
- Suggestions: alle 30s (Zeile 540)

### State Machine (Zeile 405)
```
idle → recording → processing → completed
                  → failed
         paused (nur lokaler State)
```

---

## 6. Bekannte Bugs (aus Code)

| Bug | Datei:Zeile | Beschreibung |
|-----|-------------|--------------|
| Speaker Heuristic falsch | `transcription_tasks.py:374` | Order Heuristic: Speaker 0 → erster Teilnehmer (auch wenn falsch) |
| Feedback asyncpg Loop | `feedback_tasks.py` | `_process_feedback_async()` Crashes mit "attached to different loop" |
| `_run_async` Risiko | `transcription_tasks.py:44-50` | `get_event_loop()` kann falschen Loop zurückgeben |
| Recording Pause fake | `MeetingRoom.tsx:741-746` | Nur lokaler State, Recording läuft serverseitig weiter |
| Kein WebSocket | `MeetingRoom.tsx:592,694` | Transkription/Insights via Polling (5s/8s), nicht Echtzeit |

---

## 7. Infrastruktur (aus Code)

### PostgreSQL (`config.py:12-13`)
- Driver: `postgresql+asyncpg`
- Multi-Tenancy: `client_id` auf ALLEN Queries

### Redis (`config.py:17`, `transcription_tasks.py:54-62`)
- 3 Zwecke: Celery Backend, Token Blacklist, Pipeline Pub/Sub
- Connection Pool: `max_connections=10`

### RabbitMQ (`docker-compose.yml:49-77`)
- User: `rabbit_user` / `rabbit_password`
- Ports: 5672 (AMQP), 15672 (Management)

### MinIO (`config.py:31-34`)
- Endpoint: `http://minio:9000`
- Bucket: `meeting-recordings`

### LiveKit (Frontend: `MeetingRoom.tsx:965-1001`)
- Audio-only (kein Video)
- Egress → MinIO für Recording

### n8n (`config.py:54-60`)
- Webhooks: meeting-created, audio-uploaded, transcription-completed, pv-validated, etc.

---

## 8. Tests

- **Gesamt:** 349/354 (98.6%)
- **E2E:** `docker-compose.e2e.yml` mit `E2E_TEST=true`
- **Unit:** `pytest tests/ --ignore=tests/e2e/`
- **Known:** 5 Pre-existing Failures

---

## 9. Security (ISO 27001)

- **Multi-Tenancy:** `client_id` auf ALLEN Queries (Zeile 145, 270, 869, 907)
- **Audit:** `AuditService.log_action()` für Pipeline-Events (Zeile 154, 252, 276, 579, 733, 1027, 1059, 1080)
- **Encryption:** Fernet auf PV/Transcription Spalten
- **JWT:** httpOnly Cookies + X-Client-ID Header
