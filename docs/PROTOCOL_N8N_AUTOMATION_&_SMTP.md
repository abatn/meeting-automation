# PROTOKOLL: N8N-AUTOMATISIERUNG & KOMMUNIKATIONS-HUB

Datum: 20.02.2026 - 02.03.2026
Status: Abgeschlossen

🎯 ZIEL
Implementierung einer zuverlässigen Benachrichtigungs-Infrastruktur für Meeting-Einladungen, Protokoll-Versand und Aufgaben-Reminders mittels n8n.

🔧 TECHNOLOGIEN
- n8n Workflow Engine
- SMTP (Email Protocol)
- WhatsApp Business API (Simulation)
- FastAPI Webhooks

📝 DURCHGEFÜHRTE KORREKTUREN

### 1. Workflow-Portabilität & SMTP Fix
- **Problem:** Abhängigkeit von proprietären SendGrid-Knoten verhinderte den Start der Workflows in Standard-n8n-Umgebungen.
- **Lösung:** Vollständige Migration aller Email-Aktionen auf den universellen SMTP-Knoten. Nutzung der zentralen Zugangsdaten aus der `.env`-Datei.
- **Workflows:** `meeting-created.json`, `daily-reminders.json` und `transcription-completed.json`.

### 2. Backend-Integration
- **Webhook-Trigger:** Implementierung der Service-Logik im Backend (MeetingService, RecordingService), die gezielt n8n-Endpunkte anspricht.
- **X-Internal-API-Key:** Absicherung der Kommunikation zwischen n8n und dem Backend durch einen statischen API-Key zur Erfüllung von ISO 27001 Standards.

### 3. Workflow-Stabilisierung
- **Aktivierung:** Dokumentation der Notwendigkeit der manuellen Aktivierung im n8n-Dashboard zur Freischaltung der Production-Webhooks.
- **JSON-Syntax:** Korrektur von Maskierungsfehlern in N8N-Ausdrücken, um den fehlerfreien Import der Workflow-Dateien zu ermöglichen.

⚠️ HERAUSFORDERUNGEN & LÖSUNGEN
- **404 Webhook-Fehler:** Identifiziert als Status-Problem (inaktive Workflows) nach System-Resets. Gelöst durch Benutzer-Anleitung und Aktivierungs-Checks.
- **Credential Persistence:** Sicherstellung, dass SMTP- und WhatsApp-Credentials nach einem Volume-Wipe manuell in der UI nachgepflegt werden.

### 4. Produktions-Finalisierung (März 2026)
- **Payload-Synchronisierung:**
  - Anpassung des Backends (`MeetingService`), um Teilnehmerlisten als `attendees` Array (E-Mail-Adressen) zu senden.
  - Implementierung von `.join(',')` Logik in n8n-Ausdrücken, um die Kompatibilität mit Standard-SMTP-Servern sicherzustellen.
- **Credential Mapping:**
  - Identifizierung der realen SMTP-Zugangsdaten in der n8n-Datenbank (ID: `eHaPFftWKgcTTXQc`).
  - Festschreibung dieser IDs in allen 3 Workflow-Dateien zur Vermeidung von "Credential not found" Fehlern.
- **Automatisierter Deployment-Prozess:**
  - Integration von CLI-Befehlen (`n8n import:workflow` und `publish:workflow`) zur massenhaften Aktivierung ohne manuelle UI-Klicks.
  - Aktivierung via SQL-Injection in der Tabelle `workflow_entity` zur Sicherstellung der Betriebsbereitschaft nach Container-Restarts.

📊 ERGEBNIS (März 2026)
✅ **Meeting Invitation (ID 2):** Aktiv & Verifiziert (HTTP 200 via Backend-Simulation).
✅ **Transcription Notification (ID 3):** Aktiv. Nutzt neue `/automation/pdf` Endpunkte zum Versand fertiger Protokolle.
✅ **Daily Reminders (ID 4):** Aktiv. Nutzt angereicherte Daten (Telefon/Manager-Email) aus dem Backend.
✅ **Gesamtsystem:** Die automatisierte Kommunikationskette ist nun vollständig in die Produktion integriert und getestet.

---

## 🔄 P1 CRITICAL ISSUES – N8N & BACKEND ERWEITERUNGEN (April 2026)

### 5. Neue Workflows & Webhooks
- **Audio Uploaded** (`audio-uploaded`): Wird nach MinIO/S3-Upload getriggert, startet Transkription via n8n → Whisper/Mistral.
- **Meeting Status Changed** (`meeting-status-changed`): Wird bei Status-Änderungen (in_progress, completed, cancelled) getriggert, sendet E-Mail-Benachrichtigungen.
- **PV Validated** (`pv-validated`): Wird nach finaler Freigabe des Protokolls getriggert, verteilt finales PDF.
- **Pipeline-Shift**: n8n dient nur noch als Notification Hub; alle KI-Analysen erfolgen im Celery-Backend.

### 6. Assignment Matching (Fuzzy)
- **Implementiert in**: `backend/app/tasks/transcription_tasks.py:_save_pv_and_actions` (Zeilen 246-259)
- **Logik**: Fuzzy-Matching von Assignee-Namen gegen `User.full_name` und `User.email` mittels `ILIKE '%{assignee}%'` (case-insensitive Substring).
- **Fallback**: Wenn kein User gefunden → externe Assignment (`external_name`/`external_email`).
- **Multi-Tenant**: Einschränkung auf `client_id` des Recordings.

### 7. Security Hardening – Team Management
- **PENDING-Passwörter**: Alle PENDING-User (neu eingeladen) erhalten zufällige, sichere Passwort-Hashes (`secrets.token_urlsafe(32)` + bcrypt), nicht mehr den Klartext-"PENDING_USER_NO_PASSWORD".
- **Email-Uniqueness**: Migration `c6d7e8f9a0b1` erzwingt Unique Constraint auf `(client_id, email)` in `team_members`.
- **Audit-Log**: Alle Einladungen/Re-Aktivierungen werden in `audit_logs` dokumentiert.
- **Disable statt Delete**: `delete_team_member` deaktiviert User (status=DISABLED) statt Löschen, um Audit-Trail zu erhalten.

### 8. .env Variablen (erforderlich)
```bash
# n8n Webhooks
N8N_WEBHOOK_USER_INVITED=http://n8n:5678/webhook/user-invited
N8N_WEBHOOK_MEETING_CREATED=http://n8n:5678/webhook/2/webhook/meeting-created
N8N_WEBHOOK_MEETING_STATUS_CHANGED=http://n8n:5678/webhook/meeting-status-changed
N8N_WEBHOOK_AUDIO_UPLOADED=http://n8n:5678/webhook/audio-uploaded
N8N_WEBHOOK_PV_VALIDATED=http://n8n:webhook/pv-validated
N8N_WEBHOOK_DAILY_REMINDER=http://n8n:5678/webhook/4/webhook/daily-reminders
N8N_WEBHOOK_TRANSCRIPTION_COMPLETED=http://n8n:5678/webhook/3/webhook/transcription-completed
```

### 9. Testing & Deployment Checklist
- [ ] n8n Workflows (`n8n/workflows/*.json`) in DEV und Staging importieren und **aktivieren** (Toggle → Grün).
- [ ] SMTP-Credentials in n8n UI verknüpfen (ID: `eHaPFftWKgcTTXQc` für Standard-SMTP).
- [ ] Alembic Migration `c6d7e8f9a0b1` auf allen Umgebungen ausführen (`alembic upgrade head`).
- [ ] E2E-Test: Komplette Pipeline von Meeting-Erstellung bis PV-Export validieren.
- [ ] Staging: `PUBLIC_BACKEND_URL` auf externe URL setzen (nicht `localhost`).

---
*Hinweis: Dieses Dokument fasst die Protokolle ehemals PART 11 (Teile), PART 14 und PART 16 zusammen.*
