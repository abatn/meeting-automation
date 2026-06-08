# n8n Workflow Activation Guide — Tier 1.4

**Date:** 2026-06-06
**Reason:** LiveKit-pipeline requires all 3 webhooks to be active in n8n for full automation.

---

## Why this matters

The meeting `test1631` failed downstream automation because:
- `meeting-created` webhook returned `404 Not Found`
- Error: `"The requested webhook 'POST meeting-created' is not registered. The workflow must be active for a production URL to run successfully."`

This is an n8n-side issue: the workflow JSON exists in the repo, but it is **not activated** in the running n8n instance. Workflows must be toggled "Active" in the n8n UI to receive webhooks.

---

## 3 Required Webhooks (all must be Active)

| Webhook | URL | Triggered By | File |
|---------|-----|--------------|------|
| `meeting-created` | `POST /webhook/meeting-created` | `meeting_service.py` when a new meeting is created | `n8n/workflows/meeting-created.json` |
| `audio-uploaded` | `POST /webhook/audio-uploaded` | `recording_service.py` after chunked upload completes (old MediaRecorder path) | `n8n/workflows/audio-uploaded.json` |
| `transcription-completed` | `POST /webhook/transcription-completed` | `transcription_tasks.py` after Gladia + Speaker ID | `n8n/workflows/transcription-completed.json` |

---

## Activation Procedure (Manual, One-Time)

### Step 1: Open n8n UI

The n8n instance is exposed on port 5678 (production) or 5679 (E2E). Open in browser:

- **Production:** `http://<host>:5678`
- **E2E:** `http://<host>:5679`

Login with the n8n admin credentials (set in `docker-compose.yml` `N8N_*` env vars, default `admin/changeme`).

### Step 2: Import each workflow

For each of the 3 files listed above:

1. Click **Workflows** in the left sidebar
2. Click **Import from File** (top right)
3. Select the JSON file from `n8n/workflows/`
4. The workflow appears in the list with status **Inactive**

### Step 3: Activate each workflow

1. Click on the imported workflow
2. Toggle the **Active** switch in the top right (turns green)
3. Verify the **Production URL** appears in the Webhook node (e.g., `http://n8n:5678/webhook/meeting-created`)
4. Save the workflow

### Step 4: Verify webhook registration

From the backend container, test each webhook:

```bash
docker exec meeting-automation-backend-1 \
  curl -s -o /dev/null -w "meeting-created: %{http_code}\n" \
  -X POST http://n8n:5678/webhook/meeting-created \
  -H "Content-Type: application/json" \
  -d '{"meeting_id":"test","title":"test"}'

docker exec meeting-automation-backend-1 \
  curl -s -o /dev/null -w "audio-uploaded: %{http_code}\n" \
  -X POST http://n8n:5678/webhook/audio-uploaded \
  -H "Content-Type: application/json" \
  -d '{"recording_id":"test","meeting_id":"test"}'

docker exec meeting-automation-backend-1 \
  curl -s -o /dev/null -w "transcription-completed: %{http_code}\n" \
  -X POST http://n8n:5678/webhook/transcription-completed \
  -H "Content-Type: application/json" \
  -d '{"transcription_id":"test","meeting_id":"test"}'
```

**Expected:** All three return `200` (or `500` if the test payload is invalid, but NOT `404`).

**Failed:** If any return `404`, the workflow is not active — go back to Step 3.

---

## Permanent Fix (Future)

The workflows should be **auto-activated** when n8n starts. Two options:

### Option A: n8n API activation
Add a small script that runs on n8n startup and activates all workflows via the n8n REST API:

```bash
# /opt/n8n-activate.sh
for workflow_file in /home/node/.n8n/workflows/*.json; do
  curl -X POST http://localhost:5678/api/v1/workflows \
    -H "X-N8N-API-KEY: $N8N_API_KEY" \
    -H "Content-Type: application/json" \
    -d @$workflow_file
done
```

This requires `N8N_API_KEY` to be set and the API to be enabled (`N8N_PUBLIC_API_ENABLED=true`).

### Option B: Mark workflows active in the JSON
Set the `active: true` field in each workflow JSON before mounting it. n8n will then activate on first load.

Currently the JSONs have `active: false`. Editing them to `active: true` and re-importing solves this permanently.

---

## Verification Checklist (after activation)

- [ ] `meeting-created` returns 200 from backend
- [ ] `audio-uploaded` returns 200 from backend
- [ ] `transcription-completed` returns 200 from backend
- [ ] Creating a new meeting triggers the `meeting-created` workflow (check n8n UI → Executions)
- [ ] No more `404 Not Found` errors in backend logs

---

## Rollback

If a workflow causes problems, deactivate it in the n8n UI. The backend will receive `404` (or `500` if the workflow errors), but will not crash — the `meeting_service.py` already handles webhook failures gracefully.

---

## References

- See `docs/LIVEKIT_PRODUCTION_HARDENING_ROADMAP.md` Tier 1.4 for context
- See `n8n/workflows/` for workflow JSON files
- See `backend/app/services/meeting_service.py` for webhook trigger
