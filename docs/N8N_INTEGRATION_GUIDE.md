# n8n Integration Guide: Meeting Automation System

This guide explains how the backend services interact with n8n workflows for automated processing.

## 1. Overview

The backend uses `HTTP POST` webhooks to trigger n8n workflows. n8n processes the data (often involving AI services) and calls back the backend webhooks to update the state.

## 2. Configured Webhooks

| Workflow | Event | Backend Trigger | n8n Webhook URL |
| :--- | :--- | :--- | :--- |
| **Meeting Created** | `meeting.created` | `MeetingService.create_meeting` | `N8N_WEBHOOK_MEETING_CREATED` |
| **Transcription Completed**| `transcription.completed`| `transcription_tasks._notify_n8n_completion` | `N8N_WEBHOOK_TRANSCRIPTION_COMPLETED` |
| **Daily Reminders**| `daily_reminders` | `daily_reminder_task` (Celery) | `N8N_WEBHOOK_DAILY_REMINDER`|

## 3. Callback Endpoints

*Hinweis: Da die KI-Verarbeitung nun komplett im Backend stattfindet, ruft n8n keine Callbacks mehr auf, um Transkripte oder PVs zurückzusenden. n8n fungiert nur noch als Empfänger von Webhooks für den E-Mail/WhatsApp-Versand.*

## 4. Setup in n8n

1. **Import Workflows**: Load `.json` files from `n8n/workflows/`.
2. **Credentials**: 
   - Set up `HTTP Request` nodes with `N8N_AUTH_USER` and `N8N_AUTH_PASSWORD`.
   - Configure S3/Minio credentials for file access.
   - Configure WhatsApp Business API tokens.
3. **Environment**: Ensure n8n can reach the `BACKEND_CALLBACK_URL`.