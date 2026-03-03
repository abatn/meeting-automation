PROTOKOLL: PART_17_SECURITY_ADJUSTMENTS

Datum: 22.02.2026
Status: Abgeschlossen

🎯 ZIEL
Anpassung der Sicherheitsmechanismen für n8n-Automatisierungsendpunkte, um einen reibungslosen Ablauf ohne manuelle Benutzer-Tokens zu ermöglichen.

🔧 TECHNOLOGIEN
- FastAPI (Backend)
- SQLAlchemy (Async)
- cURL (Testing)

📝 DURCHGEFÜHRTE ARBEITSSCHRITTE
1. Analyse der Authentifizierung in `backend/app/api/v1/actions.py`.
2. Identifizierung des Endpunkts `/api/v1/actions/pending` als kritisch für n8n (Daily Reminders).
3. Entfernung der `get_current_user` Abhängigkeit für diesen spezifischen Endpunkt.
4. Neustart des Backend-Containers und Verifizierung via cURL.
5. Erfolgreicher Test: Endpunkt liefert leere Liste `[]` (da keine pending actions in der Test-DB) statt eines 401/403 Fehlers zurück.

⚠️ HERAUSFORDERUNGEN & LÖSUNGEN
- Herausforderung: Shell-Syntax Fehler bei der Ausführung komplexer Befehlsketten mit XML-Escaping.
- Lösung: Direkte Ausführung im Terminal ohne überflüssiges Escaping von Sonderzeichen wie `&`.

🔗 ZUSAMMENHANG ZUM PROJEKT
Ermöglicht dem n8n Workflow "Daily Reminders", fällige Aktionen automatisiert abzurufen, ohne dass ein administrativer Benutzer permanent eingeloggt sein muss oder ein Token erneuert werden muss.

📊 ERGEBNIS
Der Endpunkt `/api/v1/actions/pending` ist nun öffentlich (oder für das interne Docker-Netzwerk) zugänglich. Für eine Produktionsumgebung wird empfohlen, diesen Zugriff über IP-Whitelisting oder einen statischen API-Key abzusichern.

**Update n8n Workflows:**
- Die Datei `n8n/workflows/daily-reminders.json` wurde aktualisiert: Die Authentifizierung im Node "Get Pending Actions" wurde auf `none` gesetzt, da das Backend nun keinen Token mehr für diesen Pfad benötigt.

---

### UPDATE: Phase 3 Audit Security Hardening (27.02.2026)

Im Rahmen des umfassenden System-Audits wurden die in diesem Dokument beschriebenen "öffentlichen" Endpunkte gehärtet, um ISO 27001 Compliance (A.9.4.1) zu gewährleisten.

**Zusätzliche Sicherheitsmaßnahmen:**
1. **API-Key Enforcement:** Die Endpunkte `/api/v1/actions/pending` sowie alle Webhooks unter `/api/v1/webhooks/` sind nun durch den Header `X-Internal-API-Key` geschützt.
2. **Audit-Log Erweiterung:** Die `AuditMiddleware` wurde aktualisiert, um die `user_id` aus dem JWT-Token zu extrahieren und im Audit-Log zu speichern. Nicht authentifizierte Requests werden als `anonymous` geloggt.
3. **Internal Secret:** Das genutzte Secret ist in der `config.py` unter `INTERNAL_API_SECRET` definiert und muss in n8n-Workflows als Header hinterlegt werden.

**Verifizierung:**
- `curl` ohne Key -> 403 Forbidden ✅
- `curl` mit validem Key -> 200 OK ✅
- Audit-Logs enthalten nun die korrekte `user_id` für alle modifizierenden Aktionen ✅

---

### UPDATE: Sicherer Logout & serverseitige Token-Invalidierung (01.03.2026)

Zur Erfüllung der ISO 27001 Anforderungen an die sofortige Zugriffsaufhebung wurde ein serverseitiger Logout-Mechanismus implementiert.

**Technische Umsetzung:**
1. **Redis Blacklist**: Einführung eines `AuthService` (`backend/app/services/auth_service.py`), der bei Abmeldung den JTI des JWT-Tokens in einer Redis-basierten Blacklist speichert.
2. **Middleware-Integration**: Die Authentifizierungs-Abhängigkeit (`get_current_user` in `deps.py`) prüft nun bei jedem Request, ob der präsentierte Token in Redis als "blacklisted" markiert ist.
3. **Automatisierte TTL**: Blacklist-Einträge in Redis haben eine Time-To-Live (TTL), die exakt der Restlaufzeit des Tokens entspricht, um Speicherplatz effizient zu verwalten.

**Verifizierung:**
- Login -> Token erhalten -> Zugriff auf `/me` OK ✅
- Logout -> Token wird blackgelistet ✅
- Erneuter Zugriff mit altem Token -> 401 Unauthorized (Token has been blacklisted) ✅
- Redis-Check -> Token-Existenz bestätigt ✅

**Zusammenhang zum Projekt:**
Diese Maßnahme vervollständigt das Sitzungsmanagement und verhindert, dass einmal ausgestellte Tokens nach einem Logout weiterverwendet werden können (Schutz vor Token-Hijacking).

---

### UPDATE: JWT Stabilisierung & Konfigurationshärtung (01.03.2026)

Parallel zur Blacklist wurden weitere JWT-Parameter optimiert, um die Systemstabilität zu erhöhen:

1. **Statischer `SECRET_KEY`**: Die Konfiguration wurde so angepasst, dass der `SECRET_KEY` nun zwingend aus der `.env`-Datei geladen wird. Dies verhindert die automatische Neugenerierung bei Container-Restarts, welche zuvor alle aktiven Sitzungen willkürlich beendete.
2. **Erweiterte Token-Laufzeit**: Die `ACCESS_TOKEN_EXPIRE_MINUTES` wurde von 30 auf 1440 Minuten (24 Stunden) erhöht. Dies reduziert Re-Authentifizierungs-Zyklen während langer Meetings und stabilisiert die Simulation komplexer Szenarien.
3. **Erweitertes Fehler-Logging**: Die Middleware in `deps.py` loggt nun detaillierte Stacktraces bei JWT-Validierungsfehlers, was die Fehlersuche bei abgelaufenen oder korrupten Tokens massiv beschleunigt.

**Zusammenhang zum Projekt:**
Diese Maßnahmen bilden das Fundament für eine zuverlässige Benutzererfahrung und verhindern "unbegründete" Logouts durch Infrastruktur-Events.
