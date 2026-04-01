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

### 3. Daily Reminders (`daily-reminders.json`)
- **Trigger**: Cron Schedule (Jeden Tag um 08:00 Uhr morgens).
- **Aktionen**:
    - Ruft offene und überfällige Aufgaben (Action Items) vom Backend ab (`/api/v1/actions/pending`).
    - Sendet automatisierte WhatsApp-Erinnerungen via WhatsApp Business API.
    - Eskaliert überfällige Aufgaben per E-Mail an den Manager.

### 4. User Invited (`user-invited.json`)
- **Trigger**: Webhook vom Backend (`/webhook/user-invited`), wenn ein Admin ein neues Teammitglied einlädt.
- **Aktionen**:
    - Empfängt flachen JSON-Payload (`email`, `full_name`, `company_name`, `activation_link`).
    - Sendet eine professionelle HTML-Willkommens-E-Mail inkl. Aktivierungslink via SMTP.

## Setup & Aktivierung

1. **Umgebungsvariablen**:
   Sicherstellen, dass die SMTP- und WhatsApp-Zugangsdaten in der `.env` Datei konfiguriert sind.
   - `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_HOST`
   - `WHATSAPP_PHONE_ID`, `WHATSAPP_TOKEN`

2. **Workflows in n8n aktivieren**:
   - Loggen Sie sich unter `http://localhost:5678` in n8n ein.
   - Importieren Sie die drei `.json` Dateien aus dem Verzeichnis `/n8n/workflows/` (falls nicht automatisch geschehen).
   - Verknüpfen Sie die Credentials (SMTP, Postgres, Internal API Key) in den jeweiligen Nodes.
   - **WICHTIG**: Schalten Sie den "Active" Toggle-Switch oben rechts in jedem Workflow auf **ON**. Nur dann können die Webhooks vom Backend empfangen werden (ansonsten gibt es einen `404 Not Found` Fehler im Backend-Log).