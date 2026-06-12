# Pipeline Optimization — 2026-06-12

## Status: ✅ Phase 1 + Phase 2 Complete

---

## Executive Summary

| Metrik | Vorher | Nachher | Verbesserung |
|--------|--------|---------|--------------|
| E2E Tests | 329/354 (92.9%) | **349/354 (98.6%)** | +5.7% |
| Celery Crash | MissingGreenlet in daily_reminder_task | **Behoben** | ✅ |
| ONNX Singleton | Keine Init → None embeddings | **Lazy Init** | ✅ |
| Redis Connections | 7 pro Pipeline (Leak) | **1 Shared Pool** | ✅ |
| Gladia Polling | Kein Timeout (endlos) | **300s Max + Logging** | ✅ |
| Speaker Profiles | N×M DB Queries | **N Queries** | ✅ |

---

## Phase 1: Critical Crash Fixes

### T2 — Celery asyncio.run() Fix

**Problem:** `asyncio.ensure_future(..., loop=loop)` uses deprecated `loop` param (Python 3.10+). In Celery eager mode (E2E_TEST=true), `asyncio.run()` fails because event loop already running.

**Solution:** `_run_async()` helper handles both cases:
- No event loop (normal Celery worker): `asyncio.run()`
- Event loop running (eager mode): Thread pool with new event loop

**Dateien:** `transcription_tasks.py`, `email_tasks.py`, `feedback_tasks.py`

### T6 — ONNX Singleton Lazy Init

**Problem:** Module-level `speaker_embedding_service = SpeakerEmbeddingService()` never initialized. `audio_segment_service` imported uninitialized instance → embeddings always `None`.

**Solution:**
- Lazy initialization in `extract_embedding()`
- `asyncio.Lock()` for race condition prevention
- Module-level singleton with `_initialized` guard

**Datei:** `speaker_embedding_service.py`

---

## Phase 2: Stability Fixes

### T4 — Redis Connection Pooling

**Problem:** `get_redis_client()` created new `redis.Redis.from_url()` per call. 7 `publish_status()` calls per pipeline = 7 unclosed connections.

**Solution:**
- Module-level `_redis_pool` with `ConnectionPool(max_connections=10)`
- `cleanup_redis_pool()` in pipeline `finally` block

**Datei:** `transcription_tasks.py`

### T1 — Gladia Polling Timeout Guard

**Problem:** `while True` + `sleep(5)` with no timeout. Stuck jobs loop forever, consuming Celery worker.

**Solution:**
- `MAX_POLL_SECONDS = 300` (5 min hard limit)
- `MAX_POLL_ITERATIONS = 100` (safety guard)
- Log iteration count and elapsed time per poll

**Datei:** `gladia_service.py`

### T5 — Speaker Profile Loading Optimization

**Problem:** `match_speaker()` called per speaker, each loading ALL profiles. 5 speakers × 100 profiles = 500 row loads.

**Solution:**
- `match_speaker_from_list()` method for pre-loaded profiles
- Load profiles once before batch loop, pass to all speakers
- Reduces DB queries from N×M to N

**Dateien:** `speaker_profile_service.py`, `transcription_tasks.py`

---

## Infrastructure Fixes

### E2E Environment API Keys

**Problem:** E2E docker-compose used `test-key` for Gladia/Mistral API keys → 401 Unauthorized.

**Solution:** Use real API keys from `.env` via `${MISTRAL_API_KEY}` and `${GLADIA_API_KEY}`.

**Datei:** `docker-compose.e2e.yml`

### Valid WAV Audio for Tests

**Problem:** Tests used `b"FAKE_AUDIO_DATA"` → Gladia 400 "Unsupported codec".

**Solution:** Generate valid 16kHz mono WAV (1 second silence) in `sample_audio_bytes` fixture.

**Datei:** `tests/e2e/conftest.py`

### PV Upsert Pattern

**Problem:** Pipeline always INSERT new PV → `UniqueViolationError` if PV exists.

**Solution:** Check for existing PV before insert, update if exists.

**Datei:** `transcription_tasks.py`

---

## Verbleibende Einschränkungen

| Issue | Status | Grund |
|-------|--------|-------|
| ONNX Audio Matching | ⚠️ E2E: heuristic+text | ONNX-Modell fehlt in Docker Image |
| Audit Action List | ⚠️ 1 Test fehlgeschlagen | Test erwartet alte Action-Typen |
| n8n Webhooks | ⚠️ 404 | Workflows nicht aktiviert |

---

## Dateien geändert

```
docker-compose.e2e.yml              — Echte API Keys
backend/app/tasks/transcription_tasks.py — Redis Pool + Timeout + Profile Loading + PV Upsert
backend/app/tasks/email_tasks.py     — _run_async() für eager mode
backend/app/tasks/feedback_tasks.py  — _run_async() für eager mode
backend/app/services/gladia_service.py — Timeout Guard
backend/app/services/speaker_profile_service.py — match_speaker_from_list()
backend/app/services/speaker_embedding_service.py — Lazy Init + Lock
tests/e2e/conftest.py               — Valid WAV + Fixtures
tests/e2e/test_phase7_minio_integration.py — Mock fixtures
tests/e2e/test_recording_transcription_pipeline.py — sample_audio_bytes
tests/e2e/test_tier2_pipeline_hardening.py — Import + sample_audio_bytes
tests/e2e/test_pv_generation_flow.py — MultipleResultsFound fix
tests/integration/test_meeting_workflow.py — Mock fixtures + WAV
tests/integration/test_n8n_communication.py — API Key fix
```

---

## Nächste Phasen

### Phase 3: Production-Readiness
- T3: Celery Config Hardening (task_acks_late, Queue-Isolation)
- T7: Blocking I/O in async Context (librosa, fbank, os.remove)
- T8: Fehlende DB-Indexe (15 Alembic Migration)

### Phase 4: UX
- T9: Frontend Recording State nach Redux
- T10: Parallel ffmpeg Segment-Extraktion
