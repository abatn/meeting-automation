# n8n Integration Guide: Meeting Automation System

This guide explains how the backend services interact with n8n workflows for automated processing.

## 1. Overview

The backend uses `HTTP POST` webhooks to trigger n8n workflows. n8n processes the data (often involving AI services) and calls back the backend webhooks to update the state.

**Architecture Shift (May 2026)**: n8n now serves exclusively as a **Notification Hub** for external communication (Email, WhatsApp, Calendar invitations). All AI processing (transcription, PV generation, action item extraction) happens in the backend Celery workers.

## 2. Configured Webhooks

| Workflow | Event | Backend Trigger | n8n Webhook URL | Authentication |
| :--- | :--- | :--- | :--- | :--- |
| **Meeting Created** | `meeting.created` | `MeetingService.create_meeting` | `/webhook/meeting-created` | None (public) |
| **Audio Uploaded** | `audio.uploaded` | `RecordingService.upload_audio` | `/webhook/audio-uploaded` | `X-Internal-API-Key` |
| **Meeting Status Changed**| `meeting.status_changed`| `MeetingService.update_status` | `/webhook/meeting-status-changed` | None (public) |
| **Transcription Completed**| `transcription.completed`| `transcription_tasks._notify_n8n_completion` | `/webhook/transcription-completed` | `X-Internal-API-Key` |
| **PV Validated**| `pv.validated` | `ReportService.validate_pv` | `/webhook/pv-validated` | `X-Internal-API-Key` |
| **Daily Reminders**| `daily_reminders` | `daily_reminder_task` (Celery) | `/webhook/daily-reminders` | `X-Internal-API-Key` |
| **User Invited**| `user.invited` | `TeamService.create_team_member` | `/webhook/user-invited` | None (public) |

## 3. Callback Endpoints

*Hinweis: Da die KI-Verarbeitung nun komplett im Backend stattfindet, ruft n8n keine Callbacks mehr auf, um Transkripte oder PVs zurückzusenden. n8n fungiert nur noch als Empfänger von Webhooks für den E-Mail/WhatsApp-Versand.*

## 4. Setup in n8n

### 4.1 Import Workflows

Load `.json` files from `n8n/workflows/`:

```bash
# Via n8n CLI
docker exec n8n n8n import:workflow --input /path/to/workflow.json

# Via n8n UI
1. Open n8n UI (http://localhost:5678)
2. Click "Import from File"
3. Select workflow JSON file
4. Click "Import"
```

### 4.2 Credentials

Configure the following credentials in n8n:

#### SMTP Credentials
- **Type**: SMTP
- **Host**: `SMTP_HOST` (from .env)
- **Port**: `SMTP_PORT` (from .env)
- **Username**: `SMTP_USER` (from .env)
- **Password**: `SMTP_PASSWORD` (from .env)
- **Secure**: true (for TLS)

#### WhatsApp Business API
- **Type**: HTTP Header Auth
- **Header Name**: `Authorization`
- **Header Value**: `Bearer <WHATSAPP_TOKEN>` (from .env)
- **Credential ID**: `3` (as referenced in workflows)

#### Internal API Key
- **Type**: Environment Variable
- **Variable Name**: `AUTOMATION_API_KEY`
- **Value**: Set in `.env` file
- **Usage**: Passed via `X-Internal-API-Key` header

### 4.3 Environment Variables

Ensure the following environment variables are set in the n8n container:

```bash
# n8n Configuration
N8N_HOST=0.0.0.0
N8N_PORT=5678
N8N_PROTOCOL=http
N8N_PATH=/

# Backend Communication
BACKEND_URL=http://backend:8000
AUTOMATION_API_KEY=your-secure-random-key-here

# SMTP Configuration
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-smtp-user
SMTP_PASSWORD=your-smtp-password

# WhatsApp Business API
WHATSAPP_PHONE_ID=your-phone-id
WHATSAPP_TOKEN=your-whatsapp-token
```

## 5. Backend Integration

### 5.1 Webhook Triggers

The backend triggers n8n workflows using HTTP POST requests:

```python
# Example: Meeting Created
import httpx

async def trigger_meeting_created_webhook(meeting_data: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.N8N_WEBHOOK_URL}/meeting-created",
            json=meeting_data,
            timeout=10.0
        )
        response.raise_for_status()
```

### 5.2 Authentication

For internal workflows (Audio Uploaded, Transcription Completed, PV Validated, Daily Reminders), the backend uses the `X-Internal-API-Key` header:

```python
# Example: Audio Uploaded
async def trigger_audio_uploaded_webhook(meeting_id: str, audio_url: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.N8N_WEBHOOK_URL}/audio-uploaded",
            headers={
                "X-Internal-API-Key": settings.AUTOMATION_API_KEY
            },
            json={
                "meeting_id": meeting_id,
                "audio_url": audio_url
            },
            timeout=10.0
        )
        response.raise_for_status()
```

### 5.3 Error Handling

The backend should handle webhook failures gracefully:

```python
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def trigger_n8n_webhook(url: str, payload: dict, headers: dict = None):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers or {},
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"Successfully triggered n8n webhook: {url}")
            return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Failed to trigger n8n webhook: {url}, error: {e}")
        raise
```

## 6. Workflow Payloads

### 6.1 Meeting Created

```json
{
  "title": "Weekly Team Meeting",
  "attendees": ["user1@example.com", "user2@example.com"],
  "start_time": "2026-05-06T10:00:00Z",
  "end_time": "2026-05-06T11:00:00Z",
  "description": "Weekly sync meeting"
}
```

### 6.2 Audio Uploaded

```json
{
  "meeting_id": "uuid-here",
  "audio_url": "https://minio.example.com/bucket/audio.mp3",
  "duration": 3600
}
```

### 6.3 Meeting Status Changed

```json
{
  "title": "Weekly Team Meeting",
  "status": "in_progress",
  "previous_status": "planned",
  "attendees": ["user1@example.com", "user2@example.com"],
  "start_time": "2026-05-06T10:00:00Z"
}
```

### 6.4 Transcription Completed

```json
{
  "meeting_id": "uuid-here",
  "title": "Weekly Team Meeting"
}
```

### 6.5 PV Validated

```json
{
  "meeting_id": "uuid-here"
}
```

### 6.6 User Invited

```json
{
  "email": "newuser@example.com",
  "full_name": "John Doe",
  "company_name": "Acme Corp",
  "activation_link": "https://example.com/activate/abc123"
}
```

## 7. Security Considerations

### 7.1 Authentication

- **Public Webhooks**: Meeting Created, Meeting Status Changed, User Invited
  - No authentication required
  - Consider adding rate limiting
  - Consider adding HMAC signature validation

- **Internal Webhooks**: Audio Uploaded, Transcription Completed, PV Validated, Daily Reminders
  - Require `X-Internal-API-Key` header
  - Key is stored in environment variable
  - Key should be rotated regularly

### 7.2 Network Security

- n8n should be behind a reverse proxy in production
- Use HTTPS for all webhook calls
- Implement firewall rules to restrict access
- Use Docker network isolation

### 7.3 Data Privacy

- No sensitive data should be logged
- Implement data retention policies
- Ensure GDPR compliance
- Use encryption for data at rest and in transit

## 8. Monitoring & Logging

### 8.1 n8n Logs

```bash
# View n8n logs
docker logs n8n -f

# View last 100 lines
docker logs n8n --tail 100

# Search for errors
docker logs n8n | grep ERROR
```

### 8.2 Backend Logs

```bash
# View backend logs
docker logs backend -f

# Search for webhook calls
docker logs backend | grep webhook
```

### 8.3 Metrics

Monitor the following metrics:

- Webhook success rate
- Webhook response time
- Email delivery rate
- WhatsApp message delivery rate
- Workflow execution time

## 9. Troubleshooting

### 9.1 Webhook Not Triggering

**Symptoms**: Backend logs show webhook call, but n8n doesn't execute workflow

**Solutions**:
1. Check if workflow is activated in n8n UI
2. Check webhook URL is correct
3. Check n8n container is running
4. Check network connectivity between backend and n8n

### 9.2 Authentication Failed

**Symptoms**: 401 or 403 response from n8n

**Solutions**:
1. Check `AUTOMATION_API_KEY` is set in `.env`
2. Check header is being sent correctly
3. Restart n8n container after changing `.env`

### 9.3 Email Not Sending

**Symptoms**: Workflow executes but no email received

**Solutions**:
1. Check SMTP credentials in n8n UI
2. Check email addresses are valid
3. Check SMTP server is accessible
4. Check email logs in n8n UI

### 9.4 WhatsApp Messages Not Sending

**Symptoms**: Workflow executes but no WhatsApp message received

**Solutions**:
1. Check WhatsApp credentials in n8n UI
2. Check phone number format
3. Check WhatsApp Business API is accessible
4. Check message logs in n8n UI

## 10. Best Practices

### 10.1 Development

- Use test webhooks during development
- Implement proper error handling
- Use retry logic for transient failures
- Log all webhook calls for debugging

### 10.2 Production

- Use production webhooks
- Implement monitoring and alerting
- Use rate limiting
- Implement circuit breakers
- Regular security audits

### 10.3 Maintenance

- Regularly rotate API keys
- Keep workflows up to date
- Monitor execution logs
- Test workflows regularly
- Document any changes