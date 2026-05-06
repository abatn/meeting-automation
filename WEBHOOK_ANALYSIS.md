# Meeting Automation Project - Workflow & Webhook Analysis

## 1. N8N Workflow Files

Located in: `/home/opc/meeting-automation/n8n/workflows/`

| Workflow File | Workflow ID | Purpose |
|---|---|---|
| user-invited.json | 6 | Sends activation email when new user is invited |
| meeting-created.json | 2 | Sends meeting invitations when meeting is created |
| meeting-status-changed.json | 7 | Notifies participants when meeting status changes |
| audio-uploaded.json | 1 | Triggers transcription when audio is uploaded |
| transcription-completed.json | 3 | Notifies when transcription is complete |
| pv-validated.json | 5 | Notifies when PV (Procès Verbal) is validated |
| daily-reminders.json | 4 | Sends daily reminders for pending action items (Cron-triggered) |

---

## 2. Exact Webhook Payload Structures

All webhooks are secured with `X-Internal-API-Key: super-secret-automation-key-2026` header.

### 2.1 USER-INVITED Webhook

**Trigger**: `backend/app/services/team_service.py` → when user is invited/re-invited
**URL**: `http://n8n:5678/webhook/user-invited`
**Method**: POST
**Authentication**: `X-Internal-API-Key` header

```json
{
  "email": "string",
  "full_name": "string",
  "company_name": "string",
  "activation_link": "string (URL with token)"
}
```

**Example Flow**:
- User invitation → trigger_user_invited_webhook()
- Payload validation in n8n: requires email, full_name, activation_link
- Send email via SMTP with HTML body including activation link
- Response: `{"status":"invitation_sent","email":"...","timestamp":"ISO-8601"}`

**Source**: `backend/app/utils/webhook_utils.py:7-27`

---

### 2.2 MEETING-CREATED Webhook

**Trigger**: `backend/app/services/meeting_service.py` → `_trigger_n8n_meeting_created()` 
**URL**: `http://n8n:5678/webhook/meeting-created`
**Method**: POST
**Authentication**: `X-Internal-API-Key` header

```json
{
  "id": "string (meeting UUID)",
  "title": "string",
  "description": "string|null",
  "location": "string|null",
  "start_time": "ISO-8601 datetime|null",
  "end_time": "ISO-8601 datetime|null",
  "status": "string (planned|in_progress|completed|cancelled)",
  "attendees": ["email1@example.com", "email2@example.com"],
  "participants": [
    {
      "id": "string (UUID)",
      "email": "string",
      "name": "string|null"
    }
  ]
}
```

**Example Flow**:
- Create meeting → meeting_service.create_meeting()
- Extract attendee emails from meeting.participants
- Send POST to n8n webhook
- n8n validates: requires attendees (non-empty array) and title
- Send email invitations to all attendees via SMTP
- Response: `{"status":"invitations_sent","meeting_id":"...","attendees_count":N,"timestamp":"ISO-8601"}`

**Source**: `backend/app/services/meeting_service.py:152-200`

---

### 2.3 MEETING-STATUS-CHANGED Webhook

**Trigger**: `backend/app/services/meeting_service.py` → `_trigger_n8n_meeting_status_change()`
**URL**: `http://n8n:5678/webhook/meeting-status-changed`
**Method**: POST
**Authentication**: `X-Internal-API-Key` header

```json
{
  "meeting_id": "string (UUID)",
  "status": "string (planned|in_progress|completed|cancelled)",
  "previous_status": "string",
  "attendees": ["email1@example.com", "email2@example.com"],
  "title": "string",
  "start_time": "ISO-8601 datetime|null"
}
```

**Example Flow**:
- Update meeting status → meeting_service.update_meeting()
- n8n receives webhook with new and previous status
- Generates localized subject (FR): "En cours", "Terminé", "Annulé" 
- Generates HTML email with status transition details
- Sends individual emails per attendee via SMTP
- Response: `{"status":"notification_sent","status_change":"...","timestamp":"ISO-8601"}`

**Source**: `backend/app/services/meeting_service.py:202-221`

---

### 2.4 AUDIO-UPLOADED Webhook

**Trigger**: `backend/app/services/recording_service.py` → `after_upload()`
**URL**: `http://n8n:5678/webhook/audio-uploaded`
**Method**: POST
**Authentication**: `X-Internal-API-Key` header

```json
{
  "event": "audio.uploaded",
  "recording_id": "string (UUID)",
  "meeting_id": "string (UUID)",
  "file_path": "string (S3 key)",
  "callback_url": "http://backend:8000/api/v1/webhooks/transcription-complete"
}
```

**Expected Flow**:
- n8n validates: requires meeting_id and audio_url (or uses callback_url)
- Call backend transcription endpoint or external service
- Response: `{"status":"processing"}`

**Source**: `backend/app/services/recording_service.py` (after_upload method)

---

### 2.5 TRANSCRIPTION-COMPLETED Webhook (Inbound)

**Receiver**: `backend/app/api/v1/webhooks.py` → `transcription_complete()` (lines 17-84)
**URL**: `http://backend:8000/api/v1/webhooks/transcription-complete` or `/n8n/transcription`
**Method**: POST
**Authentication**: `X-Internal-API-Key` header (verified by `verify_internal_api_key` dependency)

```json
{
  "recording_id": "string (UUID)",
  "meeting_id": "string (UUID)",
  "transcription": "string|null (full text)",
  "transcription_text": "string|null (alternative field name)"
}
```

**Processing**:
1. Validate recording exists and derive client_id from recording
2. Check idempotency: skip if transcription already exists for this recording_id
3. Create Transcription record with:
   - `id`: new UUID
   - `client_id`: derived from recording
   - `meeting_id`: from payload
   - `recording_id`: from payload
   - `full_text`: encrypted transcription content
   - `status`: "completed"
4. Update Recording.status → "transcribed"
5. Commit to database
6. Response: `{"status": "success", "message": "transcription saved"}`

**Source**: `backend/app/api/v1/webhooks.py:17-84`

---

### 2.6 PV-GENERATED Webhook (Inbound)

**Receiver**: `backend/app/api/v1/webhooks.py` → `pv_generated()` (lines 87-105)
**URL**: `http://backend:8000/api/v1/webhooks/pv-generated`
**Method**: POST
**Authentication**: `X-Internal-API-Key` header

```json
{
  "meeting_id": "string (UUID)",
  "pv_content": "string (generated PV content)"
}
```

**Processing**:
1. Validate meeting_id and pv_content provided
2. Create PV record with:
   - `meeting_id`: from payload
   - `content`: pv_content
   - `status`: "draft"
3. Commit to database
4. Response: `{"status": "success"}`

**Source**: `backend/app/api/v1/webhooks.py:87-105`

---

### 2.7 ACTIONS-EXTRACTED Webhook (Inbound)

**Receiver**: `backend/app/api/v1/webhooks.py` → `actions_extracted()` (lines 108-123)
**URL**: `http://backend:8000/api/v1/webhooks/actions-extracted`
**Method**: POST
**Authentication**: `X-Internal-API-Key` header

```json
{
  "pv_id": "string (UUID)",
  "actions": [
    {
      "title": "string",
      "description": "string|null",
      "assignee": "string (email|name)",
      "due_date": "ISO-8601 date|null"
    }
  ]
}
```

**Processing**:
1. Validate pv_id provided
2. Call ActionService.extract_actions_from_pv(pv_id, actions_list)
3. Response: `{"status": "success"}`

**Source**: `backend/app/api/v1/webhooks.py:108-123`

---

## 3. Database Schema Understanding

### 3.1 Key Tables

#### Meetings Table
```
meetings {
  id: String (PRIMARY KEY, UUID)
  client_id: String (FK→clients, required, indexed)
  title: String (required, indexed)
  description: Text (nullable)
  location: String (nullable)
  room_id: String (FK→meeting_rooms, nullable)
  status: Enum(planned|in_progress|completed|cancelled, default: planned)
  start_time: DateTime (required)
  end_time: DateTime (nullable)
  creator_id: String (FK→users, required)
  created_at: DateTime (auto-set to now())
  updated_at: DateTime (auto-updated)
  deleted_at: DateTime (nullable, for soft deletes)
}

Constraints:
- CHECK: end_time IS NULL OR end_time > start_time
- FK: client_id→clients.id (CASCADE)
- FK: creator_id→users.id
- FK: room_id→meeting_rooms.id
- Index: created_at DESC (for queries)
```

#### Participants Table
```
participants {
  id: String (PRIMARY KEY, UUID)
  meeting_id: String (FK→meetings, required)
  user_id: String (FK→users, nullable - external users don't need account)
  email: String (required, indexed)
  name: String (nullable)
  role: String (nullable - e.g., "presenter", "attendee")
}

Constraints:
- UNIQUE: (meeting_id, email) - prevent duplicates
- FK: meeting_id→meetings.id (CASCADE)
- FK: user_id→users.id (nullable)
```

#### Recordings Table
```
recordings {
  id: String (PRIMARY KEY, UUID)
  client_id: String (FK→clients, required, indexed)
  meeting_id: String (FK→meetings, required)
  file_path: String (S3 key, required)
  status: String (default: "uploaded") - uploaded|transcribing|analyzing|completed|failed
  file_size: Integer (nullable, bytes)
  duration: Float (nullable, seconds)
  format: String (nullable - e.g., "webm", "mp3")
  access_policy: String (default: "everyone") - everyone|organizer_only|specific_people
  created_at: DateTime (auto-set)
}

Constraints:
- FK: client_id→clients.id (CASCADE)
- FK: meeting_id→meetings.id (CASCADE)
- Index: (meeting_id, status)
```

#### Transcriptions Table
```
transcriptions {
  id: String (PRIMARY KEY, UUID)
  client_id: String (FK→clients, required, indexed)
  meeting_id: String (FK→meetings, required)
  recording_id: String (FK→recordings, required)
  full_text: EncryptedText (encrypted transcription content)
  language: String (nullable - detected language code)
  status: String (default: "pending") - pending|processing|completed|failed
  segments: JSON (nullable - diarization segments)
  created_at: DateTime (auto-set)
  updated_at: DateTime (auto-updated)
}

Constraints:
- FK: client_id→clients.id (CASCADE)
- FK: meeting_id→meetings.id (CASCADE)
- FK: recording_id→recordings.id (CASCADE)
- Idempotency: Check existing transcription by (recording_id, client_id) before inserting
```

### 3.2 N8N Integration Table

#### N8N Meetings Table (Created by migration b4c5d6e7f8a9)
```
n8n_meetings {
  id: String (PRIMARY KEY, UUID)
  meeting_id: String (FK→meetings.id, required)
  title: String (required)
  start_time: DateTime (nullable)
  created_at: DateTime (auto-set to now())
}
```

**Purpose**: Track meetings that have been sent to n8n for webhook processing.
**Note**: This table is created but not explicitly referenced in backend code yet - used for audit trail.

### 3.3 Related Tables

#### PV (Procès Verbal) Table
```
pv {
  id: String (PRIMARY KEY, UUID)
  meeting_id: String (FK→meetings.id, required)
  content: Text (PV content, typically markdown)
  status: String (default: "draft") - draft|published|archived
  created_at: DateTime
  updated_at: DateTime
}
```

#### Actions Table
```
actions {
  id: String (PRIMARY KEY, UUID)
  meeting_id: String (FK→meetings.id, required)
  pv_id: String (FK→pv.id, nullable)
  title: String (required)
  description: Text (nullable)
  status: String (default: "open") - open|in_progress|completed|cancelled
  due_date: DateTime (nullable)
  created_at: DateTime
  updated_at: DateTime
}

Index: (meeting_id, status) - for dashboard queries
```

---

## 4. Webhook Flow Diagram

```
OUTBOUND WEBHOOKS (Backend → N8N):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. User Invited
   UserInvitation → webhook_utils.trigger_user_invited_webhook()
   → POST to /webhook/user-invited
   → n8n: validate → send email (SMTP)
   
2. Meeting Created
   create_meeting() → _trigger_n8n_meeting_created()
   → POST to /webhook/meeting-created
   → n8n: validate → extract attendees → send emails (SMTP)

3. Meeting Status Changed
   update_meeting() → _trigger_n8n_meeting_status_change()
   → POST to /webhook/meeting-status-changed
   → n8n: validate → generate status-specific HTML → send emails (SMTP)

4. Audio Uploaded
   recording_service.after_upload()
   → POST to /webhook/audio-uploaded
   → n8n: trigger transcription service or callback

5. Daily Reminders
   n8n Cron (8 AM daily) → GET /api/v1/actions/pending
   → n8n: filter by due_date = today → send SMS/email reminders

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INBOUND WEBHOOKS (N8N → Backend):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Transcription Completed
   n8n (external service) → POST /api/v1/webhooks/transcription-complete
   → validate recording exists → create Transcription record → update Recording.status

2. PV Generated
   n8n (AI service) → POST /api/v1/webhooks/pv-generated
   → create PV record with status="draft"

3. Actions Extracted
   n8n (AI service) → POST /api/v1/webhooks/actions-extracted
   → call ActionService.extract_actions_from_pv()

4. PV Validated
   n8n workflow → webhook to backend (structure not fully exposed in code)
   Purpose: Track when PV has been validated/approved

```

---

## 5. Security Implementation

### Authentication
- **Header Required**: `X-Internal-API-Key: super-secret-automation-key-2026`
- **Dependency Injection**: `verify_internal_api_key` dependency in FastAPI routes
- **Multi-Tenant**: All webhook payloads implicitly filtered by client_id from JWT token

### Audit Logging (ISO 27001 A.12.4.1)
Each outbound webhook trigger logs to audit_log table:
```python
await AuditService.log_action(
    self.db,
    client_id=meeting.client_id,
    action="N8N_MEETING_CREATED_TRIGGERED",
    user_id=meeting.creator_id,
    table_name="meetings",
    record_id=meeting.id,
    new_values={"http_status": response.status_code, ...}
)
```

### Data Encryption
- Transcription.full_text: encrypted via EncryptedText type
- Segment text in transcription_segments: encrypted

---

## 6. File Locations Reference

### Backend Webhook Implementations
| File | Function | Webhook |
|---|---|---|
| backend/app/utils/webhook_utils.py | trigger_user_invited_webhook() | user-invited |
| backend/app/services/meeting_service.py | _trigger_n8n_meeting_created() | meeting-created |
| backend/app/services/meeting_service.py | _trigger_n8n_meeting_status_change() | meeting-status-changed |
| backend/app/services/recording_service.py | after_upload() | audio-uploaded |
| backend/app/api/v1/webhooks.py | transcription_complete() | transcription-complete (inbound) |
| backend/app/api/v1/webhooks.py | pv_generated() | pv-generated (inbound) |
| backend/app/api/v1/webhooks.py | actions_extracted() | actions-extracted (inbound) |

### N8N Workflow Files
All in: `/home/opc/meeting-automation/n8n/workflows/`
- user-invited.json (ID: 6)
- meeting-created.json (ID: 2)
- meeting-status-changed.json (ID: 7)
- audio-uploaded.json (ID: 1)
- transcription-completed.json (ID: 3)
- pv-validated.json (ID: 5)
- daily-reminders.json (ID: 4)

### Database Models
All in: `backend/app/models/`
- meeting.py (Meeting, Participant, Agenda)
- recording.py (Recording, Chunk)
- transcription.py (Transcription, Segment, Speaker)
- pv.py (PV)
- action.py (Action, Assignment)

### Configuration
- backend/app/core/config.py (webhook URLs and secrets)

---

## 7. Testing Notes

### Webhook Payload Idempotency
- **Transcription-Complete**: Checks for existing Transcription by (recording_id, client_id)
- **No duplicate key checks** for other inbound webhooks - assumes n8n handles retry logic

### E2E Testing
- Test file: `backend/tests/e2e/test_n8n_webhook_integration.py`
- Run with: `E2E_MODE=true pytest tests/e2e/test_n8n_webhook_integration.py -v`

---

**Last Updated**: 2026-05-06
**Project**: Meeting Automation SaaS
**Tech Stack**: FastAPI + SQLAlchemy + N8N + PostgreSQL

