# n8n Quickstart Guide - Meeting Automation

Dieser Guide hilft dir, deine n8n Workflows zu aktivieren und erfolgreich zu testen.

## 1. Aktivierung eines Workflows

1.  **Workflow öffnen**: Wähle den gewünschten Workflow aus der Liste in n8n aus.
2.  **Speichern**: Stelle sicher, dass alle Änderungen gespeichert sind (Disk-Icon oben rechts oder `Strg+S`).
3.  **Toggle-Schalter**: Oben rechts findest du einen Schalter (Toggle).
     - **Grau**: Inaktiv (Webhooks geben 404 zurück, außer im Test-Modus).
     - **Grün**: Aktiv (Produktions-Webhooks sind live).
4.  **Wichtig**: Ein Workflow muss gespeichert sein, bevor er aktiviert werden kann.

## 2. Test-URL vs. Produktions-URL

Wenn du den Webhook-Node öffnest, siehst du oben zwei Tabs:

-   **Test URL**:
     - Format: `http://localhost:5678/webhook-test/...`
     - **Wichtig**: Diese URL funktioniert NUR, wenn du in n8n gerade auf "Listen for event" geklickt hast. Sie ist für die Entwicklung gedacht.
-   **Production URL**:
     - Format: `http://localhost:5678/webhook/...`
     - Diese URL funktioniert dauerhaft, sobald der Workflow oben rechts auf **"Aktiv" (Grün)** steht.

## 3. Webhook-Namen im Projekt

Im Meeting Automation System sind folgende Pfade registriert (keine Workflow-IDs mehr erforderlich):

-   **Meeting Created**: `meeting-created`
-   **Audio Uploaded**: `audio-uploaded`
-   **Meeting Status Changed**: `meeting-status-changed`
-   **Transcription Completed**: `transcription-completed`
-   **PV Validated**: `pv-validated`
-   **Daily Reminders**: `daily-reminders`
-   **User Invited**: `user-invited`

**Wichtig**: Production-Webhooks antworten erst mit `200 OK`, wenn der Workflow permanent **aktiviert** wurde (Toggle oben rechts auf Grün).

Du findest alle aktiven Webhooks in n8n in der Seitenleiste unter **"Settings" -> "Webhooks"**.

## 4. Schritt-für-Schritt Test (Beispiel: Meeting Created)

1.  **Workflow aktivieren**: Öffne `meeting-created.json` in n8n und schalte den Toggle oben rechts auf **Grün**.
2.  **URL ermitteln**: Die Produktions-URL für den lokalen Docker-Container ist:
     `http://localhost:5678/webhook/meeting-created`
3.  **Test mit cURL**:
     ```bash
     curl -X POST http://localhost:5678/webhook/meeting-created \
          -H "Content-Type: application/json" \
          -d '{
            "id": "test-123",
            "title": "Test Meeting",
            "attendees": ["user@example.com"],
            "start_time": "2026-05-06T10:00:00Z"
          }'
     ```
4.  **Ergebnis**: Wenn du ein `{"message": "Workflow started"}` oder ähnliches erhältst (und kein 404), war der Test erfolgreich!

## 5. Security Setup (WICHTIG!)

### 5.1 Environment Variables konfigurieren

Bevor du Workflows aktivierst, stelle sicher, dass alle Environment Variables in der `.env` Datei konfiguriert sind:

```bash
# n8n Internal API Key (für Backend-Kommunikation)
AUTOMATION_API_KEY=your-secure-random-key-here

# SMTP Configuration
SMTP_USER=your-smtp-user
SMTP_PASSWORD=your-smtp-password
SMTP_HOST=smtp.example.com
SMTP_PORT=587

# WhatsApp Business API
WHATSAPP_PHONE_ID=your-phone-id
WHATSAPP_TOKEN=your-whatsapp-token
```

### 5.2 Credentials in n8n konfigurieren

1. **SMTP Credentials**:
   - Gehe zu n8n UI → Credentials → Add Credential
   - Wähle "SMTP"
   - Konfiguriere mit den Werten aus der `.env` Datei
   - Speichere die Credentials (ID wird automatisch generiert)

2. **WhatsApp Credentials**:
   - Gehe zu n8n UI → Credentials → Add Credential
   - Wähle "HTTP Header Auth"
   - Konfiguriere mit `Authorization: Bearer <WHATSAPP_TOKEN>`
   - Speichere die Credentials

### 5.3 Security Best Practices

✅ **Do's**:
- Verwende Environment Variables für alle Secrets
- Rotiere API Keys regelmäßig
- Aktiviere HTTPS in Produktion
- Implementiere Rate Limiting für Webhooks
- Logge alle Webhook-Aufrufe für Auditing

❌ **Don'ts**:
- Keine hard-coded Secrets in Workflow-Dateien
- Keine Secrets in Query-Parametern (nur in Headers)
- Keine `.env` Files in Git committen
- Keine schwachen Passwörter für API Keys

## 6. Workflow-Spezifische Tests

### 6.1 Meeting Created Test

```bash
curl -X POST http://localhost:5678/webhook/meeting-created \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Test Meeting",
       "attendees": ["user1@example.com", "user2@example.com"],
       "start_time": "2026-05-06T10:00:00Z"
     }'
```

**Erwartetes Ergebnis**: E-Mail an alle Teilnehmer mit Einladung

### 6.2 User Invited Test

```bash
curl -X POST http://localhost:5678/webhook/user-invited \
     -H "Content-Type: application/json" \
     -d '{
       "email": "newuser@example.com",
       "full_name": "John Doe",
       "company_name": "Acme Corp",
       "activation_link": "https://example.com/activate/abc123"
     }'
```

**Erwartetes Ergebnis**: Willkommens-E-Mail mit Aktivierungslink

### 6.3 Meeting Status Changed Test

```bash
curl -X POST http://localhost:5678/webhook/meeting-status-changed \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Test Meeting",
       "status": "in_progress",
       "previous_status": "planned",
       "attendees": ["user1@example.com"],
       "start_time": "2026-05-06T10:00:00Z"
     }'
```

**Erwartetes Ergebnis**: Status-Benachrichtigung an alle Teilnehmer

### 6.4 Transcription Completed Test

```bash
curl -X POST http://localhost:5678/webhook/transcription-completed \
     -H "Content-Type: application/json" \
     -d '{
       "meeting_id": "test-123",
       "title": "Test Meeting"
     }'
```

**Erwartetes Ergebnis**: PDF-Protokoll per E-Mail an alle Teilnehmer

## 7. Fehlerbehebung

### 7.1 404 Not Found
- Der Workflow ist nicht aktiviert (Toggle oben rechts ist noch grau).
- Du verwendest die Test-URL ohne aktives "Listening".
- **Wichtig**: Production-Webhooks (ohne `-test` im Pfad) antworten erst mit `200 OK`, wenn der Workflow permanent **aktiviert** wurde.

### 7.2 Connection Refused
- Prüfe, ob der n8n Docker-Container läuft (`docker ps`).
- Prüfe, ob der Port 5678 verfügbar ist.

### 7.3 Authentication Failed
- `AUTOMATION_API_KEY` nicht gesetzt oder falsch
- Prüfe `.env` Datei
- Starte n8n Container neu (`docker restart n8n`)

### 7.4 Email Not Sending
- SMTP Credentials nicht konfiguriert
- Prüfe n8n UI → Credentials
- Teste SMTP-Verbindung mit Test-Email

### 7.5 WhatsApp Messages Not Sending
- WhatsApp Credentials nicht konfiguriert
- Prüfe Phone ID und Token
- Teste WhatsApp API direkt

## 8. Workflow-Status prüfen

Um den Status aller Workflows zu prüfen:

```bash
# Alle aktiven Workflows auflisten
docker exec n8n n8n list:workflow

# Workflow-Details anzeigen
docker exec n8n n8n get:workflow <workflow-id>

# Workflow aktivieren
docker exec n8n n8n activate:workflow <workflow-id>

# Workflow deaktivieren
docker exec n8n n8n deactivate:workflow <workflow-id>
```

## 9. Logs und Debugging

### 9.1 Workflow-Logs anzeigen

```bash
# n8n Container Logs
docker logs n8n -f

# Letzte 100 Zeilen
docker logs n8n --tail 100
```

### 9.2 Execution-Logs in n8n UI

1. Gehe zu n8n UI → Executions
2. Wähle den Workflow aus
3. Klicke auf eine Execution um Details zu sehen
4. Prüfe Input/Output für jeden Node

### 9.3 Debug-Modus aktivieren

Um den Debug-Modus für einen Workflow zu aktivieren:

1. Öffne den Workflow in n8n UI
2. Klicke auf "Execute Workflow" (Play-Button)
3. Der Workflow läuft im Debug-Modus
4. Du kannst die Ausgabe jedes Nodes in Echtzeit sehen

## 10. Next Steps

Nachdem du alle Workflows erfolgreich getestet hast:

1. ✅ Alle Workflows in Produktion aktivieren
2. ✅ Monitoring und Alerting einrichten
3. ✅ Backup-Strategie implementieren
4. ✅ Dokumentation für Team-Mitglieder teilen
5. ✅ Regelmäßige Security-Audits planen