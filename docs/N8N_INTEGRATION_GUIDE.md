# n8n Integration Guide: Meeting Automation System

This guide explains how the backend services interact with n8n workflows for automated processing.

## 1. Overview

The backend uses `HTTP POST` webhooks to trigger n8n workflows. n8n processes the data (often involving AI services) and calls back the backend webhooks to update the state.

## 2. Configured Webhooks

| Workflow | Event | Backend Trigger | n8n Webhook URL |
| :--- | :--- | :--- | :--- |
| **Meeting Created** | `meeting.created` | `MeetingService.create_meeting` | `N8N_WEBHOOK_URL` |
| **Audio Uploaded** | `audio.uploaded` | `RecordingService.upload_audio` | `N8N_WEBHOOK_AUDIO_UPLOAD` |
| **PV Validated** | `pv.validated` | `PVService.validate_pv` | `N8N_WEBHOOK_PV_VALIDATED` |
| **Daily Reminders**| `daily_reminders` | `daily_reminder_task` (Celery) | `N8N_WEBHOOK_DAILY_REMINDER`|

## 3. Callback Endpoints

n8n workflows must send results back to the following endpoints in `backend/app/api/v1/webhooks.py`:

### POST `/api/v1/webhooks/transcription-complete`
**Payload:**
```json
{
  "recording_id": "uuid",
  "meeting_id": "uuid",
  "transcription": "Text content..."
}
```

### POST `/api/v1/webhooks/pv-generated`
**Payload:**
```json
{
  "meeting_id": "uuid",
  "pv_content": "Draft text..."
}
```

### POST `/api/v1/webhooks/actions-extracted`
**Payload:**
```json
{
  "pv_id": "uuid",
  "actions": [
    {
      "title": "Task 1",
      "assignee_email": "user@example.com",
      "due_date": "2024-12-31"
    }
  ]
}
```

## 4. Setup in n8n

1. **Import Workflows**: Load `.json` files from `n8n/workflows/`.
2. **Credentials**: 
   - Set up `HTTP Request` nodes with `N8N_AUTH_USER` and `N8N_AUTH_PASSWORD`.
   - Configure S3/Minio credentials for file access.
   - Configure WhatsApp Business API tokens.
3. **Environment**: Ensure n8n can reach the `BACKEND_CALLBACK_URL`.