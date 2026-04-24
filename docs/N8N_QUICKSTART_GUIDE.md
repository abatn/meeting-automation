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
           "participants": [{"email": "user@example.com"}]
         }'
    ```
4.  **Ergebnis**: Wenn du ein `{"message": "Workflow started"}` oder ähnliches erhältst (und kein 404), war der Test erfolgreich!

## Fehlerbehebung
-   **404 Not Found**: 
    - Der Workflow ist nicht aktiviert (Toggle oben rechts ist noch grau).
    - Du verwendest die Test-URL ohne aktives "Listening".
    - **Wichtig**: Production-Webhooks (ohne `-test` im Pfad) antworten erst mit `200 OK`, wenn der Workflow permanent **aktiviert** wurde.
-   **Connection Refused**: Prüfe, ob der n8n Docker-Container läuft (`docker ps`).