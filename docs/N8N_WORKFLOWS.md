# n8n Workflow Integration

This document describes the automated workflows managed by n8n within the Meeting Automation System.

## Architektur-Shift: n8n als Notification Hub

Nach der System-Stabilisierung und Migration auf Deepgram (bzw. Whisper/Mistral im Backend) wird n8n **nicht mehr für die KI-Verarbeitung** genutzt. Alle Audio- und Textanalysen finden exklusiv im Celery-Worker des Backends statt.

n8n dient nun ausschließlich als **orchestrator für externe Kommunikation** (E-Mail, WhatsApp, Kalender-Einladungen).

## Aktive Workflows

### 1. Meeting Created (`meeting-created.json`)
- **Trigger**: Webhook vom Backend (`/webhook/meeting-created`), wenn ein neues Meeting geplant wird.
- **Aktionen**:
    - Speichert Metadaten in einer n8n-Hilfstabelle (`n8n_meetings`) via Postgres.
    - Sendet eine Einladungs-E-Mail an alle Teilnehmer via SMTP.

### 2. Transcription Completed (`transcription-completed.json`)
- **Trigger**: Webhook vom Backend (`/webhook/transcription-completed`), sobald die KI (Deepgram/Mistral) das Protokoll fertiggestellt hat.
- **Aktionen**:
    - Ruft über die interne Backend-API (`/api/v1/reports/automation/...`) die finalen Meeting-Details ab.
    - Lädt das fertig generierte PDF-Protokoll vom Backend herunter.
    - Sendet das PDF-Protokoll als E-Mail-Anhang an alle Teilnehmer via SMTP.

### 3. Audio Uploaded (`audio-uploaded.json`)
- **Trigger**: Webhook vom Backend (`/webhook/audio-uploaded`), nachdem eine Meeting-Aufnahme zu MinIO/S3 hochgeladen wurde.
- **Aktionen**:
    - Startet die Transkriptions-Pipeline (Whisper/Mistral) mit der Audio-Datei.
    -送往 Backend-Callback-URL nach Abschluss (`/api/v1/webhooks/transcription-complete`).

### 4. Daily Reminders (`daily-reminders.json`)
- **Trigger**: Cron Schedule (Jeden Tag um 08:00 Uhr morgens).
- **Aktionen**:
    - Ruft offene und überfällige Aufgaben (Action Items) vom Backend ab (`/api/v1/actions/pending`).
    - Sendet automatisierte WhatsApp-Erinnerungen via WhatsApp Business API.
    - Eskaliert überfällige Aufgaben per E-Mail an den Manager.

### 5. User Invited (`user-invited.json`)
- **Trigger**: Webhook vom Backend (`/webhook/user-invited`), wenn ein Admin ein neues Teammitglied einlädt.
- **Aktionen**:
    - Empfängt flachen JSON-Payload (`email`, `full_name`, `company_name`, `activation_link`).
    - Sendet eine professionelle HTML-Willkommens-E-Mail inkl. Aktivierungslink via SMTP.

### 6. Meeting Status Changed (`meeting-status-changed.json`)
- **Trigger**: Webhook vom Backend (`/webhook/meeting-status-changed`), wenn sich der Meeting-Status ändert (geplant → in_progress → completed).
- **Aktionen**:
    - Sendet eine Status-Benachrichtigung an alle Teilnehmer (E-Mail).
    - Unterschiedliche Templates für: in_progress ("Réunion démarrée"), completed ("Réunion terminée"), cancelled ("Réunion annulée").

### 7. PV Validated (`pv-validated.json`)
- **Trigger**: Webhook vom Backend (`/webhook/pv-validated`), wenn das Protokoll final freigegeben wurde.
- **Aktionen**:
    - Ruft Meeting-Details vom Backend ab.
    - Lädt das finale PDF-Protokoll herunter.
    - Sendet das PDF als E-Mail-Anhang an alle Teilnehmer.
- **Status**: ✅ Produktiv (PDF-Attachment Fix: 09.05.2026)
- **Konfiguration**:
    - HTTP Request Node: `options.response.responseFormat: "file"`, `outputPropertyName: "data"`
    - Email Send Node: `options.attachments: "data"`

## Setup & Aktivierung

### 1. Umgebungsvariablen

Sicherstellen, dass die SMTP- und WhatsApp-Zugangsdaten in der `.env` Datei konfiguriert sind.

```bash
# SMTP Configuration
SMTP_USER=your-smtp-user
SMTP_PASSWORD=your-smtp-password
SMTP_HOST=smtp.example.com

# WhatsApp Business API
WHATSAPP_PHONE_ID=your-phone-id
WHATSAPP_TOKEN=your-whatsapp-token

# n8n Internal API Key (for backend communication)
AUTOMATION_API_KEY=your-secure-api-key
```

### 2. Workflows in n8n aktivieren

1. Loggen Sie sich unter `http://localhost:5678` in n8n ein.
2. Importieren Sie die `.json` Dateien aus dem Verzeichnis `/n8n/workflows/` (falls nicht automatisch geschehen).
3. Verknüpfen Sie die Credentials (SMTP, Postgres, Internal API Key) in den jeweiligen Nodes.
4. **WICHTIG**: Schalten Sie den "Active" Toggle-Switch oben rechts in jedem Workflow auf **ON**. Nur dann können die Webhooks vom Backend empfangen werden (ansonsten gibt es einen `404 Not Found` Fehler im Backend-Log).

## Security Best Practices

### ✅ Implemented (May 2026)

1. **No Hard-coded Secrets**: All API keys and secrets are now stored in environment variables (`AUTOMATION_API_KEY`)
2. **Header-based Authentication**: Internal API communication uses `X-Internal-API-Key` header instead of query parameters
3. **JSON Syntax Validation**: All workflows have been validated for correct JSON structure
4. **Expression Syntax**: Fixed `$()` syntax errors, now using proper `$node[]` syntax

### 🔒 Security Recommendations

1. **Environment Variables**: Never commit `.env` files to version control
2. **Credential Rotation**: Rotate `AUTOMATION_API_KEY` regularly
3. **Webhook Validation**: Consider adding HMAC signature validation for webhook endpoints
4. **Rate Limiting**: Implement rate limiting for webhook endpoints to prevent abuse
5. **Audit Logging**: Log all webhook triggers and responses for security auditing

## Testing

### E2E Test Results (May 2026)

All workflows have been tested and validated:

- ✅ **JSON Validation**: All 7 workflows have valid JSON syntax
- ✅ **Required Fields**: All workflows have required fields (name, nodes, connections)
- ✅ **Security**: No hard-coded secrets found
- ✅ **Environment Variables**: All workflows use environment variables for secrets
- ✅ **Syntax**: No `$()` syntax errors found

### Manual Testing

To test a workflow manually:

```bash
# Test Meeting Created
curl -X POST http://localhost:5678/webhook/meeting-created \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Test Meeting",
       "attendees": ["user@example.com"],
       "start_time": "2026-05-06T10:00:00Z"
     }'

# Test User Invited
curl -X POST http://localhost:5678/webhook/user-invited \
     -H "Content-Type: application/json" \
     -d '{
       "email": "newuser@example.com",
       "full_name": "John Doe",
       "company_name": "Acme Corp",
       "activation_link": "https://example.com/activate"
     }'
```

## Troubleshooting

### Common Issues

1. **404 Not Found on Webhook**
   - Workflow is not activated (Toggle is gray)
   - Solution: Activate workflow in n8n UI

2. **Authentication Failed**
   - `AUTOMATION_API_KEY` not set or incorrect
   - Solution: Check `.env` file and restart n8n container

3. **Email Not Sending**
   - SMTP credentials not configured
   - Solution: Configure SMTP credentials in n8n UI

4. **WhatsApp Messages Not Sending**
   - WhatsApp Business API credentials not configured
   - Solution: Configure WhatsApp credentials in n8n UI

## Maintenance

### Regular Tasks

1. **Weekly**: Check workflow execution logs for errors
2. **Monthly**: Review and rotate API keys
3. **Quarterly**: Update workflow templates and test all workflows
4. **Annually**: Review and update security best practices

### Backup & Restore

To backup workflows:

```bash
# Export all workflows
docker exec n8n n8n export:workflow --all --output /tmp/workflows-backup.json

# Import workflows
docker exec n8n n8n import:workflow --input /tmp/workflows-backup.json
```