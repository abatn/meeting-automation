# LiveKit Pipeline — Production Hardening Roadmap

**Date:** 2026-06-06
**Status:** Tier 1 ✅ COMPLETE (verified 16:10 UTC), Tier 2 pending
**Trigger:** test1631 meeting analysis revealed critical S3 upload + DB integrity issues

---

## Context: Why this Roadmap Exists

On 2026-06-06, the meeting `test1631` (room `7efe88f8-d8d4-45ff-8402-b3d0bf628182`, client `a23f6d45-e62f-4c9b-8972-d3984a80448a`) was recorded via LiveKit Egress. The recording captured 44.38 seconds of clean audio (1909 packets emitted, 0 dropped), but the entire downstream pipeline **never executed**.

**Root cause analysis** (see `docs/LIVEKIT_EGRESS_ICE_FIX_2026-06-06.md` for the ICE fix history):

| Problem | Impact | Severity |
|---------|--------|----------|
| S3 URL is virtual-host-style (`meeting-recordings.minio:9000`) | DNS lookup fails, upload aborted, file never in MinIO | **Critical** |
| Recording status set to `uploaded` BEFORE webhook confirms | Data integrity bug — DB says "uploaded" but file is missing | **Critical** |
| `egress_failed` event ignored | User has no feedback that recording failed | **High** |
| n8n `meeting-created` webhook returns 404 | Downstream automation (emails, calendar) broken | **High** |
| Webhook is not idempotent | LiveKit retries cause duplicate Celery tasks | **Medium** |
| No egress health monitoring | Egress crashes go unnoticed | **Medium** |
| No recording-retry endpoint | Failed recordings require manual DB fix | **Medium** |
| No ISO 27001 audit for `egress_failed` | Compliance gap | **High** |
| No Prometheus metrics | Production observability gap | **Medium** |
| No frontend recording-status badge | UX gap | **Medium** |
| No toast notifications for pipeline completion | UX gap | **Low** |
| No real-time Gladia streaming | Future improvement, not a regression | **Deferred** |

---

## Roadmap Structure

The work is split into **4 Tiers**, each with:
- **Goal** — what we're delivering
- **Files** — exact files touched
- **Code changes** — concrete code references
- **E2E test** — how we verify success
- **Acceptance criteria** — done = ?
- **Rollback** — how to revert

After each Tier, we run the full E2E test suite against `docker-compose.e2e.yml` (port 8001) and verify against the production stack at port 8000. Only then do we proceed to the next Tier.

---

## Tier 1 — Critical Bug Fixes (P0, Day 1)

**Goal:** Make the LiveKit → MinIO → Celery pipeline actually work end-to-end.

**Status:** ✅ COMPLETE 2026-06-06 16:10 UTC (verified end-to-end on E2E stack port 8001)

**Verification result** (Meeting `10745322-128b-44ba-b47c-39d6792ea220`, Egress `EG_9qAseTG23GZo`):
```
audit_logs (record_id=d1682359-7f45-4912-aa55-06e3ee9de96b):
  LIVEKIT_RECORDING_STARTED   dg-test-user-id   meeting_id=10745322..., egress_id=EG_9qAseTG23GZo
  LIVEKIT_RECORDING_STOPPED   dg-test-user-id   meeting_id=10745322..., egress_id=EG_9qAseTG23GZo
  LIVEKIT_EGRESS_FAILED       (null)            egress_id=EG_9qAseTG23GZo, error="Start signal not received"
recordings.status: failed
```

**Sub-fixes added during Tier 1.5 (discovered while verifying 1.3):**
- 1.5a: LiveKit `webhook` config (`livekit.yaml`, `livekit-e2e.yaml`) — `urls: [...]` not `url: ...`
- 1.5b: DNS hostname in webhook URL is the docker-compose **service name** (`backend`), not container name (`meeting-automation-backend-e2e`)
- 1.5c: Backend webhook handler supports LiveKit JWT auth (protobuf `WebhookReceiver`) + Bearer `INTERNAL_API_SECRET` fallback for manual tests
- 1.5d: Corrected `EgressStatus.EGRESS_STATUS_FAILED` → `EGRESS_FAILED` (enum name in livekit-api 1.1.0)
- 1.5e: `EGRESS_ABORTED` also routes to the failure branch (otherwise Celery starts on a non-existent file)
- 1.5f: `user_id=None` in `LIVEKIT_EGRESS_*` audit log entries (FK to `users.id`; no user context in webhook)

### Fix 1.1 — S3 Path-Style URL
**Problem:** LiveKit builds S3 URL as `<bucket>.<endpoint>` = `meeting-recordings.minio:9000`, but Docker DNS only resolves `minio`.

**File:** `backend/app/services/livekit_service.py:60-77`

**Change:** Add `file_output.s3.force_path_style = True` after `file_output.s3.region = "us-east-1"`.

**E2E Test:** Trigger recording → check MinIO bucket for the file → verify URL is `minio:9000/meeting-recordings/...ogg` in Egress logs.

**Acceptance:** Egress log shows `egress_completed` (not `egress_failed`), file present in MinIO, Celery `process_recording` task triggered.

**Rollback:** Revert the 1-line change in `livekit_service.py`, restart backend.

---

### Fix 1.2 — DB Integrity: Status only via Webhook
**Problem:** `stop_livekit_recording` sets `recording.status = "uploaded"` BEFORE the file is actually in MinIO. If the upload fails, the DB still says "uploaded".

**File:** `backend/app/api/v1/livekit.py:117-126`

**Change:** Remove `recording.status = "uploaded"` from `stop_livekit_recording` (the stop endpoint only stops Egress, it does not confirm upload). Status update stays in the webhook handler at line 194.

**E2E Test:** Trigger recording, stop Egress, but simulate upload failure → verify DB status remains `streaming`, not `uploaded`.

**Acceptance:** DB `recordings.status` lifecycle is: `streaming` → `uploaded` (only after webhook) → `processed` (only after pipeline).

**Rollback:** Re-add the `recording.status = "uploaded"` line in `stop_livekit_recording`.

---

### Fix 1.3 — `egress_failed` Event Handler
**Problem:** When Egress fails (S3 error, network error, etc.), LiveKit sends `egress_failed` webhook. The current handler only processes `egress.completed`, so the failed recording is silently ignored.

**File:** `backend/app/api/v1/livekit.py:177-208`

**Change:** Add an `elif event == "egress_failed"` branch that:
1. Looks up the recording by `meeting_id` + `status="streaming"`
2. Sets `recording.status = "failed"`
3. Logs ISO 27001 audit entry: `LIVEKIT_EGRESS_FAILED`
4. Logs the error message from the webhook payload

**E2E Test:** Force an Egress failure (e.g., bad credentials) → verify `recording.status = "failed"` in DB + audit log entry.

**Acceptance:** Failed recordings have a clear `failed` status, error is logged, user can see the failure in the UI (Tier 4).

**Rollback:** Remove the new `elif` branch.

---

### Fix 1.4 — n8n Workflow Activation
**Problem:** The `meeting-created` webhook returns 404 because the n8n workflow is not activated. This breaks downstream automation (calendar invites, email notifications).

**File:** `docs/LIVEKIT_N8N_WORKFLOWS.md` (new, contains activation instructions)

**Change:** Document the manual activation step in n8n UI. No code change.

**E2E Test:** Create a meeting → verify `n8n meeting-created` returns 200 (not 404).

**Acceptance:** All 3 n8n webhooks active:
- `meeting-created` (from `meeting_service.py`)
- `audio-uploaded` (from `recording_service.py`, only fires on old path)
- `transcription-completed` (from `transcription_tasks.py`)

**Rollback:** Deactivate workflows in n8n UI.

---

## Tier 2 — Pipeline Hardening (P1, Week 1)

**Goal:** Make the pipeline resilient to transient failures and operational gaps.

### Fix 2.1 — Webhook Idempotency
**Problem:** LiveKit retries failed webhooks up to 5x. Without idempotency, `process_recording.delay()` runs multiple times per recording.

**Files:**
- `backend/app/models/recording.py` — add `egress_id` column with unique index
- `backend/alembic/versions/XXXX_add_egress_id.py` — Alembic migration
- `backend/app/api/v1/livekit.py:177-208` — check if already processed

**E2E Test:** Send the same webhook 3x → verify only 1 `process_recording` task runs.

**Acceptance:** Same `egress_id` triggers Celery max once. Subsequent webhooks are 200 OK but no-ops.

**Rollback:** Drop unique index, remove check in webhook handler.

---

### Fix 2.2 — Recording-Retry Endpoint
**Problem:** Failed recordings (Gladia API down, Mistral error) require manual DB intervention to retry.

**Files:**
- `backend/app/api/v1/recordings.py` — add `POST /recordings/{id}/retry`
- `frontend/src/components/meetings/RecordingStatus.tsx` — Retry button (UI deferred to Tier 4)

**E2E Test:** Set a recording to `status="failed"` → call retry endpoint → verify `process_recording.delay()` is called.

**Acceptance:** Authenticated user can retry their own failed recordings (max 3 attempts, audit-logged).

**Rollback:** Remove the endpoint, revert to manual intervention.

---

### Fix 2.3 — Egress Health Monitoring
**Problem:** Egress container can OOM-crash. Currently no alert.

**Files:**
- `backend/app/services/health_service.py` (new) — polls Egress `/health` every 30s
- `backend/app/api/v1/health.py` — expose `egress_status` in `/health` response
- `frontend/src/components/layout/ServiceStatus.tsx` (new, deferred to Tier 4)

**E2E Test:** Stop Egress container → verify `/health` returns 503 with `egress_status: down` within 60s.

**Acceptance:** `/health` reports Egress availability. Backed by Prometheus metric (Tier 3.1).

**Rollback:** Remove the periodic poll task.

---

### Fix 2.4 — S3 Multipart Upload for Large Files
**Problem:** Long meetings (1h+) may produce OGG files >5MB. LiveKit Egress uses PutObject, which is fine, but adding multipart via SDK config can improve reliability for >100MB files.

**Files:**
- `livekit-egress.yaml` — configure `s3.upload_part_size`

**E2E Test:** Record a 1-hour meeting (or simulate with 50MB file) → verify upload completes without timeout.

**Acceptance:** Recordings up to 1h upload reliably without manual intervention.

**Rollback:** Remove the config change.

---

## Tier 3 — Observability & ISO 27001 Audit (P1, Week 2)

**Goal:** Production-grade observability and compliance.

### Fix 3.1 — Prometheus Metrics
**Files:**
- `backend/app/api/v1/metrics.py` (new) — `/metrics` endpoint
- `backend/app/services/metrics_service.py` (new) — counter/histogram helpers
- `backend/app/tasks/transcription_tasks.py` — instrumentation
- `backend/app/api/v1/livekit.py` — instrumentation
- `prometheus/prometheus.yml` (new) — scrape config

**Metrics:**
- `recordings_total{status}` (counter)
- `egress_duration_seconds` (histogram)
- `gladia_transcription_duration_seconds` (histogram)
- `pv_generation_duration_seconds` (histogram)
- `webhook_received_total{event, status}` (counter)

**Acceptance:** `/metrics` returns Prometheus-format data. Grafana dashboard can be built.

**Rollback:** Remove the metrics endpoint, revert instrumentation.

---

### Fix 3.2 — ISO 27001 Audit Completeness
**Files:**
- `backend/app/api/v1/livekit.py:165-209` — add audit for `egress_failed`, `webhook_rejected`, `webhook_received`

**New audit events:**
- `LIVEKIT_EGRESS_FAILED` (with error message)
- `LIVEKIT_WEBHOOK_RECEIVED` (for all events)
- `LIVEKIT_WEBHOOK_REJECTED` (invalid secret)

**Acceptance:** All webhook interactions have an audit trail. ISO 27001 audit reports show complete coverage.

**Rollback:** Remove the new audit calls.

---

### Fix 3.3 — Structured JSON Logging
**Files:**
- `backend/app/core/logging.py` (new) — JSON formatter
- `docker-compose.yml` — set `LOG_FORMAT=json` for backend

**Acceptance:** Logs are machine-parseable. Loki/ELK can aggregate them.

**Rollback:** Revert to text format.

---

## Tier 4 — User Experience (P2, Week 3)

**Goal:** Make the recording pipeline visible and trustworthy to end users.

### Fix 4.1 — Recording-Status Badge
**File:** `frontend/src/components/meetings/MeetingRoom.tsx`

Status badge: 🟡 Streaming → 🟢 Uploaded → 🔵 Transcribing → 🟣 PV Ready → ✅ Done / 🔴 Failed.

### Fix 4.2 — Toast Notifications
**File:** `frontend/src/hooks/usePipelineNotifications.ts` (new)

Backend pushes WebSocket event on pipeline completion.

### Fix 4.3 — Failed-Recording Modal
**File:** `frontend/src/components/meetings/FailedRecordingModal.tsx` (new)

Shows: "Was ist passiert?" + Retry button.

### Fix 4.4 — Service-Status Indicator
**File:** `frontend/src/components/layout/ServiceStatus.tsx` (new)

Shows Egress availability from `/health` endpoint.

**Acceptance:** Users see real-time recording pipeline progress, can retry failed recordings, see service health.

**Rollback:** Remove frontend components.

---

## Tier 5 — Future (P3, Q3 2026)

**Goal:** Long-term improvements. Not in current scope but documented for planning.

- **Real-time Gladia streaming** — WebSocket-based, replace batch transcription
- **Multi-region Egress replicas** — for global deployment
- **Custom Egress worker** — only if LiveKit OSS limits are hit
- **Recording encryption at rest** — KMS-managed keys
- **Egress session recording metrics** — per-meeting resource usage

---

## Verification Process (After Each Tier)

1. **Code changes** — apply the fix
2. **E2E test in `docker-compose.e2e.yml`** (port 8001) — run `pytest tests/e2e/test_livekit_integration.py -v`
3. **Production stack** — switch to `docker-compose.yml` (port 8000), trigger real meeting via ngrok
4. **Container logs** — verify expected log entries
5. **DB inspection** — verify state transitions
6. **MinIO inspection** — verify file presence
7. **Documentation** — update the roadmap with results

If any check fails, rollback immediately and investigate.

---

## Current Status

| Tier | Status | Tests | Last Update |
|------|--------|-------|-------------|
| Tier 1 | 🚧 In Progress | ⏳ Pending | 2026-06-06 |
| Tier 2 | ⏸️ Not Started | — | — |
| Tier 3 | ⏸️ Not Started | — | — |
| Tier 4 | ⏸️ Not Started | — | — |
| Tier 5 | 📋 Planned | — | — |
