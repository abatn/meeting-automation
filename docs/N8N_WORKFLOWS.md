# n8n Workflow Integration

**Last Updated:** 2026-06-25 (Phase 75)
**Deployment:** k3s `meeting-automation-staging` namespace
**n8n Version:** 2.27.4
**Client ID:** `e052b451-0cc3-4932-9c68-7c46240b1936`

## Architecture

n8n serves as the **notification hub** for external communication (Email, WhatsApp). All AI/audio processing is handled by the Celery worker in the backend.

```
Backend (FastAPI) → Webhook → n8n → SMTP/WhatsApp → External
                     ↓
              Celery Worker (direct)
```

### Infrastructure

| Component | Service | Access |
|-----------|---------|--------|
| n8n UI | `n8n-staging` Deployment | `http://158.180.18.110:31678` |
| n8n Webhook | `n8n-staging` Service (ClusterIP) | `http://n8n-staging:5678/webhook/*` |
| n8n Database | PostgreSQL (`meeting_db_staging`) | Shared with backend |
| SMTP Credential | `ZVhIkSAZhgZHT2pK` ("SMTP Account") | Configured in n8n UI |

## Active Workflows (6)

> **Important:** Automation API requires `?client_id=` parameter. n8n only activates 3/7 workflows on startup — others need `POST /api/v1/workflows/{id}/activate`. DB changes don't propagate to n8n in-memory state — DELETE + RE-IMPORT required.

### 1. User Invited (`user-invited`) — ID: `CqkpcBkdkXlJtZbo`
- **Trigger:** Webhook `POST /webhook/user-invited`
- **Backend Caller:** `email_tasks.py:156` (send_invitation_email)
- **Payload:** `{email, full_name, company_name, activation_link}`
- **Actions:** Validate payload → Send HTML invitation email via SMTP
- **Status:** ✅ Production (fixed 2026-06-24: responseMode=onReceived, credentials fixed)

### 2. Meeting Created (`meeting-created`) — ID: `uB0bPHLt0FNxsaBe`
- **Trigger:** Webhook `POST /webhook/meeting-created`
- **Backend Caller:** `meeting_service.py:194`
- **Actions:** Store metadata in `n8n_meetings` table → Send invitation email to participants
- **Status:** ✅ Active (credentials fixed 2026-06-24)

### 3. Meeting Status Changed (`meeting-status-changed`) — ID: `6jsJVqySI9VpnvoO`
- **Trigger:** Webhook `POST /webhook/meeting-status-changed`
- **Backend Caller:** `meeting_service.py:236`
- **Actions:** Send status notification email (in_progress/completed/cancelled)
- **Status:** ✅ Active (credentials fixed 2026-06-24)

### 4. Transcription Completed (`transcription-completed`) — ID: `00tDUsvHjpnWD6oG`
- **Trigger:** Webhook `POST /webhook/transcription-completed`
- **Backend Caller:** `transcription_tasks.py:1147`
- **Actions:** Fetch meeting details → Download PDF → Send as email attachment
- **Status:** ✅ Active (credentials fixed 2026-06-24)

### 5. PV Validated (`pv-validated`) — ID: `o9NXKZqiDnksQeO3`
- **Trigger:** Webhook `POST /webhook/pv-validated`
- **Backend Caller:** `pv_service.py:392`
- **Actions:** Fetch meeting details → Download final PDF → Send as email attachment
- **Status:** ✅ Active

### 6. Daily Reminders (`daily-reminders`) — ID: `GpER66AvYwapRNP4`
- **Trigger:** Cron schedule (08:00 daily)
- **Backend Caller:** None (n8n self-triggering)
- **Actions:** Poll `/api/v1/actions/pending` → Send WhatsApp reminders → Escalate overdue tasks via email
- **Status:** ✅ Active (cron-triggered, NOT webhook-triggered)

## Deactivated Workflows (1)

### Audio Uploaded (`audio-uploaded`) — DEPRECATED
- **Reason:** Redundant with Celery pipeline (`process_recording.delay()`)
- **Old flow:** n8n webhook → call backend API → start transcription
- **Current flow:** Backend → Celery task directly (`recording_service.py:83`)
- **Deactivated:** 2026-06-24 (Phase 63)

## Backend Config Constants

| Constant | Value | Used By |
|----------|-------|---------|
| `N8N_WEBHOOK_URL` | `http://n8n:5678/webhook` | Base URL for path construction |
| `N8N_WEBHOOK_USER_INVITED` | `.../webhook/user-invited` | `email_tasks.py`, `webhook_utils.py` |
| `N8N_WEBHOOK_MEETING_CREATED` | `.../webhook/meeting-created` | `meeting_service.py` |
| `N8N_WEBHOOK_MEETING_STATUS_CHANGED` | `.../webhook/meeting-status-changed` | `meeting_service.py` |
| `N8N_WEBHOOK_PV_VALIDATED` | `.../webhook/pv-validated` | `pv_service.py` |
| `N8N_WEBHOOK_TRANSCRIPTION_COMPLETED` | `.../webhook/transcription-completed` | `transcription_tasks.py` |

**Removed (Phase 63):**
- `N8N_WEBHOOK_AUDIO_UPLOADED` — workflow deactivated
- `N8N_WEBHOOK_DAILY_REMINDER` — n8n uses cron, not webhook

## Dead Webhook Calls (Commented Out)

These backend calls were firing to the base URL (no path) → 404. No matching n8n workflows exist.

| Event | File:Line | Status |
|-------|-----------|--------|
| `action.assigned` | `action_service.py:408` | Commented out (TODO) |
| `action.status_updated` | `action_service.py:479` | Commented out (TODO) |
| `action.escalate` | `action_service.py:986` | Commented out (TODO) |
| `_send_reminder_via_n8n` | `email_tasks.py:29-37` | Disabled (Celery task never triggered) |
| `_daily_reminder_task` webhook | `email_tasks.py:49-55` | Disabled (n8n runs own cron) |

## Setup & Activation

### k3s Deployment

n8n runs as a k3s Deployment in `meeting-automation-staging` namespace:

```bash
# Check n8n pods
kubectl get pods -n meeting-automation-staging -l app=n8n-staging

# Check n8n logs
kubectl logs -n meeting-automation-staging -l app=n8n-staging --tail=50

# Restart n8n (after workflow changes)
kubectl rollout restart deployment n8n-staging -n meeting-automation-staging
```

### n8n API (Workflow Management)

```bash
N8N_API_KEY="<from n8n-staging env>"

# List all workflows
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" http://158.180.18.110:31678/api/v1/workflows

# Get specific workflow
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" http://158.180.18.110:31678/api/v1/workflows/<id>

# Update workflow (PUT)
curl -s -X PUT "http://158.180.18.110:31678/api/v1/workflows/<id>" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"...","nodes":[...],"connections":{...},"settings":{...}}'

# Deactivate via DB (API doesn't support active=false via PATCH)
kubectl exec -n meeting-automation-staging postgres-staging-0 -- psql -U meeting_user -d meeting_db_staging -c \
  "UPDATE workflow_entity SET active = false WHERE name = '<workflow-name>';"
```

### Credential Management

SMTP credentials are stored in the n8n database (`credentials_entity` table):

```bash
# List credentials
kubectl exec -n meeting-automation-staging postgres-staging-0 -- psql -U meeting_user -d meeting_db_staging -c \
  "SELECT id, name, type FROM credentials_entity;"

# Current SMTP credential: ZVhIkSAZhgZHT2pK ("SMTP Account")
```

**Important:** When importing workflows from JSON files, credential IDs must match the target n8n instance. Broken credential IDs cause `Credential with ID "xxx" does not exist for type "smtp"` errors.

## Troubleshooting

### 1. "Credential does not exist for type smtp"
- **Cause:** Workflow references a credential ID that doesn't exist in the n8n database
- **Fix:** Update the workflow's node credentials via n8n API or DB:
  ```bash
  # Find broken credentials
  psql -c "SELECT name, nodes::text FROM workflow_entity WHERE nodes::text LIKE '%broken-id%';"
  
  # Fix: replace broken ID with correct one (ZVhIkSAZhgZHT2pK)
  psql -c "UPDATE workflow_entity SET nodes = replace(nodes::text, 'broken-id', 'ZVhIkSAZhgZHT2pK')::jsonb WHERE nodes::text LIKE '%broken-id%';"
  
  # Also fix workflow_history
  psql -c "UPDATE workflow_history SET nodes = replace(nodes::text, 'broken-id', 'ZVhIkSAZhgZHT2pK')::jsonb WHERE nodes::text LIKE '%broken-id%';"
  
  # Restart n8n
  kubectl rollout restart deployment n8n-staging -n meeting-automation-staging
  ```

### 2. "Response Data option 'success' is not supported"
- **Cause:** `Respond to Webhook` node has `respondWith: "success"` (invalid value)
- **Fix:** Change Webhook node `responseMode` to `"onReceived"` and remove the `Respond to Webhook` node

### 3. 404 on Webhook
- **Cause:** Workflow not activated
- **Fix:** Activate in n8n UI or set `active = true` in DB

### 4. Email not arriving
- **Cause:** SMTP credentials not configured or incorrect
- **Check:** n8n UI → Settings → Credentials → SMTP Account
- **Check logs:** `kubectl logs -n meeting-automation-staging -l app=n8n-staging | grep -i smtp`

### 5. Execution shows "error" but email was sent
- **Cause:** `Respond to Webhook` node failed after SMTP succeeded
- **Impact:** Email delivered, but n8n reports execution as error
- **Fix:** Use `responseMode: "onReceived"` instead of `Respond to Webhook` node

### 6. "ENOTFOUND" on Backend API Call
- **Cause:** Workflow references wrong hostname (`meeting-automation-backend-1:8000`)
- **Fix:** Update URL in n8n DB:
  ```bash
  kubectl exec -n meeting-automation-staging postgres-staging-0 -- psql -U meeting_user -d meeting_db_staging -c \
    "UPDATE workflow_entity SET nodes = replace(nodes::text, 'meeting-automation-backend-1:8000', 'backend.meeting-automation-staging.svc.cluster.local:8000')::jsonb WHERE nodes::text LIKE '%meeting-automation-backend-1%';"
  
  # Restart n8n
  kubectl rollout restart deployment n8n-staging -n meeting-automation-staging
  ```
- **Correct URL:** `backend.meeting-automation-staging.svc.cluster.local:8000`

## Testing

### Manual Webhook Test

```bash
# Test user-invited (should return 200)
curl -X POST http://158.180.18.110:31678/webhook/user-invited \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "full_name": "Test User",
    "company_name": "Test Corp",
    "activation_link": "https://staging.meeting-automation.com/activate?token=test"
  }'
```

### Check Execution Status

```bash
# Recent executions
kubectl exec -n meeting-automation-staging postgres-staging-0 -- psql -U meeting_user -d meeting_db_staging -c \
  "SELECT e.id, e.status, w.name, e.\"startedAt\" FROM execution_entity e JOIN workflow_entity w ON e.\"workflowId\" = w.id ORDER BY e.\"startedAt\" DESC LIMIT 10;"
```

## Maintenance

### Weekly
- Check execution logs for errors: `SELECT status, count(*) FROM execution_entity GROUP BY status;`
- Verify all 6 active workflows remain activated

### Monthly
- Review n8n version and update if needed
- Rotate SMTP credentials if required

### Backup

Workflows are stored in PostgreSQL (`workflow_entity` table). To backup:

```bash
# Export all workflows
kubectl exec -n meeting-automation-staging postgres-staging-0 -- psql -U meeting_user -d meeting_db_staging -c \
  "SELECT name, nodes, connections, active FROM workflow_entity;" > n8n-workflows-backup.sql
```
