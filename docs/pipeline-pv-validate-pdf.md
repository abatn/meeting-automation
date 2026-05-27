# PV Validate → PDF Email Pipeline

## Flow Overview

```
Frontend (Validate Button)
    ↓ POST /api/v1/pv/{pv_id}/validate
Backend (pv.py endpoint)
    ↓ pv_service.validate_pv()
    ↓ Sets: is_validated=True, status="published"
    ↓ _notify_validation()
    ↓ POST → N8N_WEBHOOK_PV_VALIDATED
n8n Webhook (pv-validated)
    ↓ Normalize Payload
    ↓ GET /api/v1/reports/automation/meeting/{meeting_id}
    ↓ GET /api/v1/reports/automation/pdf/{meeting_id}
    ↓ Send Email with PDF attachment
Attendees receive email with PDF ✅
```

## Step-by-Step

### 1. Frontend → PVValidator.tsx
- **File**: `frontend/src/components/meetings/PVValidator.tsx`
- **Button**: "Approve & Sign" (line 285-304)
- **Handler**: `handleApprove()` (line 99-112)
- **API Call**: `POST /api/v1/pv/{pvId}/validate`

### 2. Backend → pv.py
- **File**: `backend/app/api/v1/pv.py` (line 259-264)
- **Endpoint**: `POST /{pv_id}/validate`
- **Auth**: JWT + client_id filtering

### 3. Backend → pv_service.py
- **File**: `backend/app/services/pv_service.py` (line 202-231)
- **Method**: `validate_pv()`
- **Changes**:
  - `pv.is_validated = True`
  - `pv.validated_by_id = user_id`
  - `pv.validated_at = datetime.utcnow()`
  - `pv.status = "published"`
- **Notification**: `_notify_validation()` → POST to n8n webhook
- **Payload**: `{"event": "pv.validated", "pv_id": pv.id, "meeting_id": pv.meeting_id}`

### 4. n8n → pv-validated workflow
- **File**: `n8n/workflows/pv-validated.json`
- **Webhook**: `POST /webhook/pv-validated`
- **Nodes**:
  1. **Webhook** → receives payload
  2. **Normalize Payload** → validates meeting_id exists
  3. **Get Meeting Details** → `GET /api/v1/reports/automation/meeting/{meeting_id}`
  4. **Download PDF** → `GET /api/v1/reports/automation/pdf/{meeting_id}` (responseFormat: file)
  5. **Send Email with PDF** → SMTP email with PDF attachment to all attendees

### 5. Config
- **Webhook URL**: `http://n8n:5678/webhook/pv-validated`
- **Internal API Key**: `super-secret-automation-key-2026`
- **SMTP Credentials**: ID `Z4QPw36ZE0HkHiHP` (SMTP account)

## Key Files

| Layer | File | Purpose |
|-------|------|---------|
| Frontend | `frontend/src/components/meetings/PVValidator.tsx` | Validate button + UI |
| Frontend | `frontend/src/components/meetings/MeetingRoom.tsx` | Meeting room container |
| Backend API | `backend/app/api/v1/pv.py` | PV endpoints |
| Backend Service | `backend/app/services/pv_service.py` | Validation logic + n8n notification |
| Backend Config | `backend/app/core/config.py` | N8N_WEBHOOK_PV_VALIDATED URL |
| n8n Workflow | `n8n/workflows/pv-validated.json` | PDF download + email automation |

## Status
- ✅ Webhook registered and active
- ✅ All 3 workflows (user-invited, meeting-created, pv-validated) working
- ✅ DB migration: abc123def456 (head)
- ✅ Celery worker: healthy, no errors
