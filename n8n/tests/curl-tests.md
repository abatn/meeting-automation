# N8N Workflow Curl Test Commands

## Configuration

```bash
# Set these environment variables for testing
export N8N_URL="http://localhost:5678"
export BACKEND_URL="http://localhost:8000"
export AUTOMATION_API_KEY="your-api-key-here"
```

---

## 1. Audio Uploaded Webhook

**Workflow**: `audio-uploaded.json`
**Path**: `/webhook/audio-uploaded`
**Method**: POST
**Purpose**: Trigger transcription pipeline when audio is uploaded to meeting

### Valid Request

```bash
curl -X POST http://localhost:5678/webhook/audio-uploaded \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_id": "meeting-20260506-001",
    "audio_url": "https://s3.example.com/meeting-20260506-001/audio.mp3",
    "duration_seconds": 3600,
    "format": "mp3"
  }' \
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected Response** (HTTP 200):
```json
{
  "status": "transcription_started",
  "meeting_id": "meeting-20260506-001",
  "timestamp": "2026-05-06T10:00:00.000Z"
}
```

### Error Handling Test - Missing Required Field

```bash
curl -X POST http://localhost:5678/webhook/audio-uploaded \
  -H "Content-Type: application/json" \
  -d '{
    "audio_url": "https://s3.example.com/audio.mp3"
  }' \
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected Response** (HTTP 200 with error status):
```json
{
  "status": "error",
  "error_message": "Missing required fields: meeting_id and audio_url are required",
  "timestamp": "2026-05-06T10:00:00.000Z"
}
```

---

## 2. Meeting Created Webhook

**Workflow**: `meeting-created.json`
**Path**: `/webhook/meeting-created`
**Method**: POST
**Purpose**: Send meeting invitations to attendees

### Valid Request

```bash
curl -X POST http://localhost:5678/webhook/meeting-created \
  -H "Content-Type: application/json" \
  -d '{
    "body": {
      "meeting_id": "meeting-20260506-002",
      "title": "Team Standup",
      "description": "Daily synchronization meeting",
      "start_time": "2026-05-06T10:00:00Z",
      "end_time": "2026-05-06T10:30:00Z",
      "location": "Conference Room A",
      "attendees": [
        "alice@example.com",
        "bob@example.com",
        "charlie@example.com"
      ]
    }
  }' \
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected Response** (HTTP 200):
```json
{
  "status": "invitations_sent",
  "meeting_id": "meeting-20260506-002",
  "attendees_count": 3,
  "timestamp": "2026-05-06T10:00:00.000Z"
}
```

### Error Handling Test - Missing Attendees

```bash
curl -X POST http://localhost:5678/webhook/meeting-created \
  -H "Content-Type: application/json" \
  -d '{
    "body": {
      "meeting_id": "meeting-20260506-002",
      "title": "Team Standup",
      "start_time": "2026-05-06T10:00:00Z",
      "attendees": []
    }
  }' \
  -w "\nHTTP Status: %{http_code}\n"
```

---

## 3. Transcription Completed Webhook

**Workflow**: `transcription-completed.json`
**Path**: `/webhook/transcription-completed`
**Method**: POST
**Purpose**: Send meeting minutes PDF to participants after transcription

### Valid Request

```bash
curl -X POST http://localhost:5678/webhook/transcription-completed \
  -H "Content-Type: application/json" \
  -d '{
    "body": {
      "meeting_id": "meeting-20260506-003",
      "transcription_id": "trans-20260506-001",
      "content": "Meeting transcript with speaker identification and timestamps...",
      "duration_seconds": 3600,
      "language": "en-US",
      "confidence_score": 0.95,
      "speaker_count": 3
    }
  }' \
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected Response** (HTTP 200):
```json
{
  "status": "email_sent",
  "meeting_id": "meeting-20260506-003",
  "timestamp": "2026-05-06T10:00:00.000Z"
}
```

---

## 4. PV Validated Webhook

**Workflow**: `pv-validated.json`
**Path**: `/webhook/pv-validated`
**Method**: POST
**Purpose**: Distribute validated meeting minutes (Procès-Verbal) to participants

### Valid Request

```bash
curl -X POST http://localhost:5678/webhook/pv-validated \
  -H "Content-Type: application/json" \
  -d '{
    "body": {
      "meeting_id": "meeting-20260506-004",
      "pv_id": "pv-20260506-001",
      "status": "validated",
      "version": 1,
      "validated_by": "user-001",
      "validated_at": "2026-05-06T11:00:00Z",
      "content_html": "<h1>Meeting Minutes</h1><p>Key discussion points and decisions...</p>"
    }
  }' \
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected Response** (HTTP 200):
```json
{
  "status": "pv_distributed",
  "meeting_id": "meeting-20260506-004",
  "timestamp": "2026-05-06T10:00:00.000Z"
}
```

---

## 5. User Invited Webhook

**Workflow**: `user-invited.json`
**Path**: `/webhook/user-invited`
**Method**: POST
**Purpose**: Send account activation invitation to new users

### Valid Request

```bash
curl -X POST http://localhost:5678/webhook/user-invited \
  -H "Content-Type: application/json" \
  -d '{
    "body": {
      "email": "newuser@example.com",
      "full_name": "John Doe",
      "company_name": "Acme Corporation",
      "role": "participant",
      "activation_link": "https://example.com/activate?token=abc123def456xyz",
      "expires_at": "2026-05-13T10:00:00Z"
    }
  }' \
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected Response** (HTTP 200):
```json
{
  "status": "invitation_sent",
  "email": "newuser@example.com",
  "timestamp": "2026-05-06T10:00:00.000Z"
}
```

---

## 6. Meeting Status Changed Webhook

**Workflow**: `meeting-status-changed.json`
**Path**: `/webhook/meeting-status-changed`
**Method**: POST
**Purpose**: Notify attendees when meeting status changes

### Valid Request - Meeting Started

```bash
curl -X POST http://localhost:5678/webhook/meeting-status-changed \
  -H "Content-Type: application/json" \
  -d '{
    "body": {
      "meeting_id": "meeting-20260506-005",
      "title": "Board Meeting",
      "status": "in_progress",
      "previous_status": "planned",
      "start_time": "2026-05-06T14:00:00Z",
      "end_time": "2026-05-06T15:00:00Z",
      "changed_by": "user-001",
      "changed_at": "2026-05-06T14:00:00Z",
      "attendees": [
        "executive1@example.com",
        "executive2@example.com"
      ]
    }
  }' \
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected Response** (HTTP 200):
```json
{
  "status": "notification_sent",
  "status_change": "in_progress",
  "timestamp": "2026-05-06T10:00:00.000Z"
}
```

### Valid Request - Meeting Completed

```bash
curl -X POST http://localhost:5678/webhook/meeting-status-changed \
  -H "Content-Type: application/json" \
  -d '{
    "body": {
      "meeting_id": "meeting-20260506-005",
      "title": "Board Meeting",
      "status": "completed",
      "previous_status": "in_progress",
      "start_time": "2026-05-06T14:00:00Z",
      "end_time": "2026-05-06T15:00:00Z",
      "changed_by": "user-001",
      "changed_at": "2026-05-06T15:00:00Z",
      "attendees": [
        "executive1@example.com",
        "executive2@example.com"
      ]
    }
  }' \
  -w "\nHTTP Status: %{http_code}\n"
```

---

## Testing With Automated Script

Run the comprehensive test suite:

```bash
# Make test script executable
chmod +x n8n/tests/workflow-test-suite.sh

# Run tests with default configuration
./n8n/tests/workflow-test-suite.sh

# Run tests with custom N8N URL
N8N_BASE_URL=http://localhost:5678 ./n8n/tests/workflow-test-suite.sh

# Run tests with both custom N8N and Backend URLs
N8N_BASE_URL=http://localhost:5678 \
BACKEND_URL=http://localhost:8000 \
./n8n/tests/workflow-test-suite.sh
```

---

## Batch Testing All Workflows

```bash
#!/bin/bash

# Test all workflows in sequence

echo "Testing all n8n workflows..."

# 1. Audio uploaded
echo "1. Testing audio-uploaded..."
curl -X POST http://localhost:5678/webhook/audio-uploaded \
  -H "Content-Type: application/json" \
  -d '{"meeting_id":"test-001","audio_url":"https://example.com/audio.mp3","duration_seconds":3600}' \
  | jq '.'

# 2. Meeting created
echo "2. Testing meeting-created..."
curl -X POST http://localhost:5678/webhook/meeting-created \
  -H "Content-Type: application/json" \
  -d '{"body":{"meeting_id":"test-002","title":"Standup","start_time":"2026-05-06T10:00:00Z","attendees":["a@test.com","b@test.com"]}}' \
  | jq '.'

# 3. Transcription completed
echo "3. Testing transcription-completed..."
curl -X POST http://localhost:5678/webhook/transcription-completed \
  -H "Content-Type: application/json" \
  -d '{"body":{"meeting_id":"test-003","transcription_id":"trans-001","content":"Transcript..."}}' \
  | jq '.'

# 4. PV validated
echo "4. Testing pv-validated..."
curl -X POST http://localhost:5678/webhook/pv-validated \
  -H "Content-Type: application/json" \
  -d '{"body":{"meeting_id":"test-004","pv_id":"pv-001","status":"validated"}}' \
  | jq '.'

# 5. User invited
echo "5. Testing user-invited..."
curl -X POST http://localhost:5678/webhook/user-invited \
  -H "Content-Type: application/json" \
  -d '{"body":{"email":"test@example.com","full_name":"Test User","company_name":"Test Corp","activation_link":"https://example.com/activate"}}' \
  | jq '.'

# 6. Meeting status changed
echo "6. Testing meeting-status-changed..."
curl -X POST http://localhost:5678/webhook/meeting-status-changed \
  -H "Content-Type: application/json" \
  -d '{"body":{"meeting_id":"test-005","title":"Meeting","status":"in_progress","previous_status":"planned","attendees":["a@test.com"]}}' \
  | jq '.'

echo "All tests completed!"
```

---

## Performance Testing

```bash
#!/bin/bash

# Load test a workflow with concurrent requests

WORKFLOW="audio-uploaded"
CONCURRENT=10
DURATION=30

echo "Load testing $WORKFLOW with $CONCURRENT concurrent requests for ${DURATION}s..."

ab -n 100 -c $CONCURRENT -p /tmp/payload.json \
  -T "application/json" \
  http://localhost:5678/webhook/$WORKFLOW

echo "Load test completed!"
```

---

## Debugging Failed Requests

```bash
# Get verbose output including headers
curl -v -X POST http://localhost:5678/webhook/audio-uploaded \
  -H "Content-Type: application/json" \
  -d '{"meeting_id":"test","audio_url":"https://example.com/audio.mp3"}' \
  | jq '.'

# Get timing information
curl -w "@curl-format.txt" -o /dev/null -s \
  -X POST http://localhost:5678/webhook/audio-uploaded \
  -H "Content-Type: application/json" \
  -d '{"meeting_id":"test","audio_url":"https://example.com/audio.mp3"}'

# Save response to file for inspection
curl -X POST http://localhost:5678/webhook/audio-uploaded \
  -H "Content-Type: application/json" \
  -d @payload.json \
  -o response.json \
  -w "Status: %{http_code}\n"

cat response.json | jq '.'
```
