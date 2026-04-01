# PROTOKOLL: PART 44 - ENTERPRISE ONBOARDING & INVITATION WORKFLOW (WAY B)

**Datum:** 01.04.2026
**Status:** Abgeschlossen ✅
**Ziel:** Implementierung eines sicheren, token-basierten Einladungssystems für neue Mitarbeiter mit strikter Mandantentrennung, dynamischer Rollenzuweisung und ISO 27001-konformen Audit-Logs.

## 🔧 TECHNOLOGIEN
- **Backend:** FastAPI, SQLAlchemy 2.0 (Enum-Mapping), Alembic (Data Migration).
- **Frontend:** React 18, Material UI (Select, MenuItem, Dialogs), Axios.
- **Workflow:** n8n (Webhook Trigger), SMTP (HTML Invitations).
- **Security:** Secrets-Token (URL-safe), Timezone-aware validation, Auto-DG assignment.

## 📝 DURCHGEFÜHRTE ARBEITSSCHRITTE

### 1. Datenbank-Härtung & Refactoring
- **User-Status:** Das Feld `is_active (bool)` im `User`-Modell wurde durch `status (String/Enum: ACTIVE, PENDING, DISABLED)` ersetzt.
- **Activation Tokens:** Neue Tabelle `activation_tokens` für zeitlich begrenzte (7 Tage), kryptografisch sichere Aktivierungs-Links.
- **Alembic Migration:** Erstellung des Skripts `0fe164eb0e4a`, das bestehende Daten sicher konvertiert.

### 2. Team-Management & Einladungslogik
- **TeamService:** 
    - `create_team_member` erstellt nun einen `PENDING` User statt eines reinen Team-Eintrags.
    - **Dynamische Rollenzuweisung**: Admins können beim Einladen zwischen `participant`, `manager` und `admin` wählen.
    - **Sicherheits-Validierung**: Das Backend blockiert explizit die Zuweisung von Plattform-Rollen (`system_admin`, `tech_admin`) über die Team-Schnittstelle.
    - Implementierung einer **Reaktivierungs-Logik**: Bereits "gelöschte" (`DISABLED`) User können erneut eingeladen werden.
    - **Fehlerbehebung (Lazy Loading)**: Konsolidierung der Objekterstellung zur Vermeidung von `sqlalchemy.exc.MissingGreenlet` Fehlern bei asynchroner Rollenzuordnung.
- **Webhook-Integration:** Implementierung von `trigger_user_invited_webhook` in `webhook_utils.py` mit flachem JSON-Payload für n8n.

### 3. n8n Workflow & Kommunikation
- **Workflow-Design:** Erstellung von `n8n/workflows/user-invited.json` zum Empfang des Webhooks.
- **HTML-Template**: Bereitstellung eines professionellen E-Mail-Templates mit dynamischen Variablen.

### 4. Frontend & Aktivierungs-Flow
- **ActivationPage**: Neue Seite `/activate` zur Token-Validierung und Passwort-Setzung.
- **Rollenauswahl im UI**: Der "Add Member" Dialog wurde um ein Dropdown-Menü zur Auswahl der technischen Rolle erweitert.
- **Lokalisierung**: Alle rollenspezifischen Begriffe wurden in Englisch, Französisch und Arabisch (RTL) übersetzt.

### 5. Mandanten-Sicherheit (Auto-DG)
- **Registrierungs-Härtung**: Der erste Nutzer eines neuen Mandanten erhält nun im `register`-Endpunkt zwingend die Rolle `dg` (Director General), unabhängig von Frontend-Eingaben. Dies stellt die Administrierbarkeit jedes neuen Tenants sicher.

## ⚠️ HERAUSFORDERUNGEN & LÖSUNGEN
- **PostgreSQL Enum-Konflikt**: Status als `String` in der DB gespeichert und über Python-Enums gemappt.
- **Lazy Loading Crash**: Fix durch Zuweisung der Rollen-Objekte *bevor* das User-Objekt der Session hinzugefügt wird.

## 🔗 ZUSAMMENHANG ZUM PROJEKT
Dieses Feature vervollständigt den Enterprise-Anspruch der SaaS-Plattform.

## 📊 ERGEBNIS
✅ End-to-End Workflow erfolgreich verifiziert.
✅ Rollenbasierte Einladung und automatische DG-Berechtigung implementiert.
