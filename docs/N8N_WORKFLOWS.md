# n8n Workflow Integration

This document describes the automated workflows managed by n8n within the Meeting Automation System.

## Workflow Overview

The system uses n8n to orchestrate complex business logic, AI processing pipelines, and external integrations (WhatsApp, Email).

### 1. Meeting Created (`meeting-created.json`)
- **Trigger**: Webhook from Backend when a new meeting is scheduled.
- **Actions**:
    - Generates a calendar invite.
    - Sends an email notification to all participants via SendGrid.
- **Webhook Path**: `meeting-created`

### 2. Audio Uploaded (`audio-uploaded.json`)
- **Trigger**: Webhook from Backend after a recording is successfully uploaded to S3.
- **Actions**:
    - Calls the Whisper AI service for Speech-to-Text.
    - Sends the resulting transcript back to the Backend API.
- **Webhook Path**: `audio-uploaded`

### 3. PV Validated (`pv-validated.json`)
- **Trigger**: Webhook from Backend when a manager validates a Procès-Verbal.
- **Actions**:
    - Uses Mistral AI to extract Action Items from the PV text.
    - Notifies assigned participants via WhatsApp Business API.
- **Webhook Path**: `pv-validated`

### 4. Daily Reminders (`daily-reminders.json`)
- **Trigger**: Cron schedule (Every day at 08:00 AM).
- **Actions**:
    - Fetches pending actions from the Backend.
    - Sends WhatsApp reminders for items due today.
    - Escalates overdue items to the manager via email.

## Setup Instructions

1. **Environment Variables**:
   Ensure the following are set in `.env`:
   - `N8N_BASIC_AUTH_USER`
   - `N8N_BASIC_AUTH_PASSWORD`
   - `WHATSAPP_PHONE_ID`
   - `WHATSAPP_TOKEN`
   - `SENDGRID_API_KEY`

2. **Importing Workflows**:
   Workflows are located in `/n8n/workflows`. They can be manually imported into the n8n UI or are automatically loaded if the `EXTERNAL_HOOK_FILES` environment variable is correctly configured in Docker.

3. **Credentials**:
   You must configure the following credentials in the n8n UI:
   - **WhatsApp Token**: Header Auth (`Authorization: Bearer <token>`)
   - **SendGrid**: API Key
   - **Backend API Key**: Header Auth for internal requests.