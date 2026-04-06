PROTOKOLL: PART_41_ONLYOFFICE_INTEGRATION

Datum: 27.03.2026
Status: In Optimierung (RTL Stabil, PDF-Sync in Arbeit)

🎯 ZIEL
Einführung eines selbst gehosteten "OnlyOffice Document Servers" (v8.3.3) zur nahtlosen Online-Bearbeitung von Meeting-Protokollen. Fokus auf ISO 27001 Konformität und stabiler RTL (Arabisch) Darstellung.

🔧 TECHNOLOGIEN
- OnlyOffice Document Server v8.3.3 (Docker)
- Python (FastAPI) & Redis (Status Tracking)
- BackgroundTasks (Asynchrone Konvertierung)
- S3 MinIO (Storage)

📝 DURCHGEFÜHRTE ARBEITSSCHRITTE

1. **Infrastruktur & Stabilität**:
   - RAM-Limit auf 4GB erhöht. Dediziertes Netzwerk `meeting_net` für stabile Websockets.
   - Arabische Schriftarten (`fonts-dejavu`, `fonts-freefont-ttf`) im Container installiert.

2. **Die "Goldene Lösung" für Arabisch (Light-RTL)**:
   - **Konzept**: Verzicht auf den fehleranfälligen "Full-RTL" Modus von OnlyOffice 8.3, der Texte oft rückwärts rendert.
   - **Backend (`pv.py`)**: Entfernung aller `document.rtl` und `features.rtl` Flags. Der Editor läuft in einer LTR-Hülle.
   - **DOCX (`docx_service.py`)**: Keine `w:bidi` oder `w:rtl` XML-Tags im Body. Ausschließlich optische Rechtsbündigkeit (`p.alignment = RIGHT`) und erzwungene Schriftart `FreeSerif` für korrekte Ligaturen.
   - **Ergebnis**: Einwandfreie Lesbarkeit und Bearbeitbarkeit arabischer Texte.

3. **Speicher- & Export-Pipeline**:
   - Umstellung des Callbacks auf FastAPIs `BackgroundTasks`.
   - Implementierung von Redis-Tracking (`pdf_converting_{pv_id}`) zur Synchronisation zwischen Save und Download.
   - Hinzufügen von strikten Cache-Busting Headern im Download-Endpunkt.

⚠️ HERAUSFORDERUNGEN & LÖSUNGEN

- **Problem: PDF-Staleness**: Trotz Redis-Warteschleife zeigte der erste PDF-Download nach einer Online-Änderung manchmal noch den alten Stand. 
- **Ursache**: OnlyOffice sendet bei Klick auf "Speichern" einen `status 6` (Forcesave). Dieser wurde bisher ignoriert. Erst beim Schließen (`status 2`) wurde gespeichert, was zu Race Conditions führte.
- **Lösung**: 
  1. **Status 6 Handling**: Der Callback-Endpunkt verarbeitet nun sowohl `status 2` als auch `status 6`.
  2. **Erzwungene Cache-Invalidierung**: Bei jedem Speichervorgang wird das alte PDF in S3 sofort gelöscht und der Redis-Status `pdf_converting_{id}` gesetzt.
  3. **Robustes Polling**: Der Download-Endpunkt prüft nun sowohl den Redis-Key als auch die S3-Metadaten (LastModified) und wartet bis zu 50 Sekunden auf die neue Version.
- **Ergebnis**: Der "First-Click-Success" beim PDF-Download nach einer Bearbeitung ist nun garantiert.
- **Wichtig bei für die setup-system.sh um das system wieder zu bauen**: # Im ONLYOFFICE Container Schriftarten installieren
	# Schriftarten installieren
	docker exec -u root meeting-automation-onlyoffice-1 apt-get update
	docker exec -u root meeting-automation-onlyoffice-1 apt-get install -y fonts-noto fonts-arabic
	# Font-Cache neu generieren
	docker exec -u root meeting-automation-onlyoffice-1 /usr/bin/documentserver-generate-allfonts.sh
	# Container neu starten
	docker restart meeting-automation-onlyoffice-1***
⚠️ PRODUKTIONS-HINWEIS: ONLYOFFICE_URL in .env
- **DEV/Test**: `ONLYOFFICE_URL=http://<VM-IP>:8081` — muss auf die extern erreichbare IP/Domain gesetzt sein, damit der **Browser** den OnlyOffice-Editor laden kann.
- **Produktion**: Diese Variable durch eine echte Domain ersetzen (z.B. `https://docs.meeting-automate.tn`) oder dynamisch aus dem Request-Host ableiten. Die temporäre VM-IP aus `.env` **muss vor dem Produktions-Deploy entfernt werden**.
- `ONLYOFFICE_BACKEND_URL=http://backend:8000` bleibt immer als Docker-interne URL (OnlyOffice→Backend Callback).

---

## Update 2026-04-06 — ARM64 Fix & Dynamische Host-Konfiguration

### Problem 1: OnlyOffice startet nicht auf ARM64 (aarch64)

**Symptom**: Container hing dauerhaft bei `Starting RabbitMQ Messaging Server` — nginx startete nie.

**Root Cause**: `onlyoffice/documentserver:latest` (x86) lief via Emulation auf ARM64. Das interne RabbitMQ (Erlang/beam) startete nicht — PID-File wurde nie erstellt, `rabbitmqctl wait --timeout 600` blockierte den Startup-Script.

**Fix in `docker-compose.yml`**:
1. Image auf `onlyoffice/documentserver:latest-arm64` gewechselt
2. Externes RabbitMQ aus dem Stack konfiguriert — internes RabbitMQ wird damit übersprungen:
```yaml
- AMQP_URI=amqp://rabbit_user:rabbit_password@rabbitmq:5672/
- AMQP_TYPE=rabbitmq
```
3. `depends_on: rabbitmq: condition: service_healthy` hinzugefügt

**Ergebnis**: nginx startet in ~30 Sekunden, `api.js` erreichbar ✅

---

### Problem 2: OnlyOffice nginx redirectete auf `http://onlyoffice/...` (Container-Hostname)

**Symptom**: Browser öffnete neuen Tab → weiße Seite. Redirect-Header zeigte `Location: http://onlyoffice/9.3.1-...` → DNS-Fehler im Browser.

**Root Cause**: OnlyOffice nginx verwendete `$hostname` (= Docker-Container-Name `onlyoffice`) für absolute Redirects.

**Fix in `docker-compose.yml`**:
```yaml
hostname: "${HOST_IP:-localhost}"
environment:
  - SERVER_NAME=${HOST_IP:-localhost}
```

---

### Problem 3: Port 8081 nicht vom Browser erreichbar

**Symptom**: `curl http://158.180.18.110:8081/...` → Timeout (exit code 28).

**Root Cause**: OCI Security Group hatte Port 8081 nicht freigegeben.

**Fix**: Ingress Rule für Port 8081/tcp in OCI Console hinzugefügt.

---

### Dynamische Host-Konfiguration (keine hardcodierten IPs)

Alle öffentlichen URLs werden jetzt aus einer einzigen Variable abgeleitet:

**`.env`**:
```bash
HOST_IP=158.180.18.110   # ← Einzige Zeile bei IP-Wechsel anpassen
```

**`docker-compose.yml` (backend environment)**:
```yaml
- ONLYOFFICE_URL=http://${HOST_IP:-localhost}:8081      # Browser → OnlyOffice JS
- ONLYOFFICE_BACKEND_URL=http://backend:8000             # OnlyOffice Server → Backend (intern)
- PUBLIC_BACKEND_URL=http://${HOST_IP:-localhost}:8000   # E-Mail-Links etc.
- FRONTEND_URL=http://${HOST_IP:-localhost}:3000
```

**Architektur-Klarstellung** (ISO 27001 relevant):
- `document.url` und `callbackUrl` verwenden `ONLYOFFICE_BACKEND_URL` (Docker-intern) ✅
- Der Browser greift **nie** direkt auf `document.url` zu — das macht der OnlyOffice-Server
- `ONLYOFFICE_URL` ist nur für das Browser-seitige Laden des Editor-JS

---

### Neustart-Anleitung (nach diesen Fixes)
```bash
# Bei IP-Wechsel:
# 1. HOST_IP in .env anpassen
# 2. Backend + OnlyOffice neu starten:
docker compose up -d backend onlyoffice
```

📊 ERGEBNIS
Der Online-Editor ist für Arabisch, Französisch und Englisch voll einsatzfähig. Das Layout ist stabil. Die PDF-Konvertierung nach manueller Änderung ist nun wasserdicht synchronisiert.
