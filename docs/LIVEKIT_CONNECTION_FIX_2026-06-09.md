# LiveKit Connection Fix Task — Change Record

Datum: 2026-06-09  
Aufgabe: LiveKit-Verbindungsfehler und Recording-State konsistent mit der bestehenden Pipeline machen.

## 1. Ziel der Aufgabe

Die UI zeigte zeitweise:

```txt
Speaking
LiveKit Connection Error
could not establish pc connection
serverUrl: ws://localhost:7880
```

Gleichzeitig konnten Recording, Transcription, Insights und AI-Ausgaben erfolgreich abgeschlossen werden.

Ziel war daher nicht, die Recording-Pipeline neu zu bauen, sondern:

1. den Frontend-State sauber mit dem echten LiveKit-Connection-State zu synchronisieren,
2. Recording nur dann zu erlauben, wenn LiveKit wirklich verbunden ist,
3. einen initialen/stale Connection Error nach erfolgreicher Verbindung zu entfernen,
4. den LiveKit Media-Path robuster zu machen,
5. hardcoded LiveKit-Secrets aus aktiven Konfigurationsdateien zu entfernen,
6. LiveKit-Webhook-Verarbeitung tenant-safe gemäß ISO-27001-Anforderungen zu machen.

## 2. Fachliche Diagnose

`ws://localhost:7880` ist nur die LiveKit-Signaling-URL. Der Fehler `could not establish pc connection` betrifft die WebRTC-Media-Verbindung, also den Browser-zu-LiveKit PeerConnection-/ICE-Pfad.

LiveKit Egress ist ein serverseitiger LiveKit-Teilnehmer. Deshalb kann Egress intern mit dem LiveKit-Server verbunden sein und `egress_started` / `egress_ended` melden, auch wenn der Browser-Teilnehmer initial einen PeerConnection-Fehler oder Timeout meldet.

Die wichtigste Korrektur war daher:

- Frontend darf Connection Error nicht dauerhaft anzeigen, wenn die Verbindung später erfolgreich ist.
- Recording darf erst starten, wenn der LiveKit-Client verbunden ist.
- LiveKit-Infrastruktur soll TCP-ICE-Fallback unterstützen.
- Secrets und Webhook-Lookups müssen tenant-safe sein.

## 3. Geänderte Dateien

### 3.1 Frontend

#### `frontend/src/components/meetings/MeetingRoom.tsx`

Geändert:

- Import von `useConnectionState` ergänzt.
- Import von `ConnectionState` aus `livekit-client` ergänzt.
- Neue Helper-Komponente `LiveKitConnectionBridge` hinzugefügt.
  - Liest den LiveKit-Connection-State innerhalb von `LiveKitRoom`.
  - Gibt den State an den Parent weiter.
- Neue States ergänzt:
  - `livekitConnectionState`
  - `livekitConnected`
- Callback `handleLiveKitConnectionState` ergänzt:
  - setzt `livekitConnected`
  - löscht `livekitError`, wenn der Zustand `Connected` ist.
- `useEffect` ergänzt:
  - synchronisiert `livekitConnected`
  - löscht `livekitError` bei erfolgreicher Verbindung.
- `LiveKitRoom` erweitert:
  - `connectOptions.peerConnectionTimeout: 60000 (verified in MeetingRoom.tsx:1069)`
  - `connectOptions.maxRetries: 3`
  - `onDisconnected` setzt `livekitConnected` auf `false`.
- Recording-Start-Button angepasst:
  - disabled, solange LiveKit nicht verbunden ist.
  - Label nutzt `meeting_assistant.connecting`, solange nicht verbunden.
- Untere Recording-Toggle-UI angepasst:
  - Start-Aktion nur bei `livekitConnected === true`.
  - bei nicht verbundener LiveKit-Session wird ein deaktivierter Lade-Indikator angezeigt.

Ziel dieser Änderungen:

- kein dauerhaft falscher `LiveKit Connection Error` mehr, wenn die Verbindung später erfolgreich ist,
- Recording-Start nur bei stabiler LiveKit-Verbindung,
- UI-Zustand entspricht dem tatsächlichen LiveKit-State.

---

### 3.2 Backend API

#### `backend/app/api/v1/livekit.py`

Geändert:

- Hardcodierte Konstanten entfernt:
  - `_LIVEKIT_API_KEY`
  - `_LIVEKIT_API_SECRET`
- `WebhookReceiver` nutzt jetzt:
  - `settings.LIVEKIT_API_KEY`
  - `settings.LIVEKIT_API_SECRET`
- `get_livekit_token()` prüft jetzt, ob LiveKit-Konfiguration vollständig ist:
  - `LIVEKIT_URL`
  - `LIVEKIT_PUBLIC_URL`
  - `LIVEKIT_API_KEY`
  - `LIVEKIT_API_SECRET`
- `start_livekit_recording()` lädt Meetings jetzt mit `client_id`-Filter:
  - `Meeting.id == meeting_id`
  - `Meeting.client_id == current_user.client_id`
- Webhook-Logging entfernt die vorherige Ausgabe von `Authorization`-Header-Teilen.
- `egress_ended` und `egress_failed` verwenden jetzt tenant-safe Recording-Lookups.
- Neue Helper-Funktionen ergänzt:
  - `_get_meeting_client_id()`
  - `_get_active_recording_for_meeting()`

Ziel dieser Änderungen:

- keine hardcoded LiveKit-Secrets im Backend,
- klare Fehlermeldung bei fehlender LiveKit-Konfiguration,
- Recording-Start nur für Meetings des eigenen Tenants,
- Webhook-Verarbeitung mit Tenant-Isolation,
- keine potenzielle Tenant-Kreuzaktualisierung bei Webhooks.

---

### 3.3 Backend Config

#### `backend/app/core/config.py`

Geändert:

LiveKit-Felder sind jetzt leer als Default, damit sie aus Env kommen müssen:

- `LIVEKIT_URL`
- `LIVEKIT_PUBLIC_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`

Ziel:

- keine hardcoded LiveKit-URLs oder Secrets in der Codebase.

---

### 3.4 LiveKit Server Config

#### `livekit.yaml`

Geändert:

- `rtc.tcp_port: 7881` ergänzt.
- LiveKit API Key/Secret nicht mehr hardcoded.
- Platzhalter eingeführt:
  - `__LIVEKIT_API_KEY__`
  - `__LIVEKIT_API_SECRET__`

Ziel:

- TCP-ICE-Fallback für WebRTC-Media-Verbindung ermöglichen.
- Secrets nur zur Laufzeit aus Environment-Variablen einsetzen.

#### `livekit-e2e.yaml (REMOVED from repo)`

Analog zu `livekit.yaml` geändert:

- `rtc.tcp_port: 7881` ergänzt.
- LiveKit API Key/Secret nur noch als Platzhalter.

Ziel:

- gleiche Konfiguration für E2E-Stack ohne Hardcoding.

---

### 3.5 LiveKit Entrypoint

#### `livekit-entrypoint.sh (REMOVED from repo)`

Geändert:

- prüft, ob `LIVEKIT_API_KEY` und `LIVEKIT_API_SECRET` gesetzt sind,
- ermittelt bevorzugt IPv4 für `NODE_IP`,
- erlaubt Override über `LIVEKIT_NODE_IP`,
- ersetzt Platzhalter in `livekit.yaml` durch echte Werte,
- schreibt generierte Config nach `/tmp/livekit.yaml`,
- startet LiveKit Server mit generierter Config.

Ziel:

- keine Secrets in YAML-Dateien speichern,
- browser-erreichbare Node-IP über Env steuerbar machen,
- IPv6-/IPv4-Probleme reduzieren.

---

### 3.6 Docker Compose

#### `docker-compose.yml`

Geändert:

- Backend bekommt LiveKit-Werte aus Environment:
  - `LIVEKIT_URL`
  - `LIVEKIT_PUBLIC_URL`
  - `LIVEKIT_API_KEY`
  - `LIVEKIT_API_SECRET`
- `livekit-server` bekommt Environment:
  - `LIVEKIT_API_KEY`
  - `LIVEKIT_API_SECRET`
  - `LIVEKIT_NODE_IP`
- `livekit-server` port mapping erweitert:
  - `"7881:7881/tcp"`
- `livekit-egress` bekommt Environment:
  - `LIVEKIT_API_KEY`
  - `LIVEKIT_API_SECRET`
  - `LIVEKIT_WS_URL`

Ziel:

- Secrets nur aus `.env`,
- TCP-ICE-Fallback freigeben,
- Egress-Konfiguration ohne hardcoded LiveKit-Key/Secret.

#### `docker-compose.e2e.yml`

Analog geändert:

- Backend-, LiveKit-Server- und Egress-Services nutzen Environment-Variablen.
- TCP-Port `7881` für LiveKit Server ergänzt.

Ziel:

- E2E-Stack mit gleicher sicherer Konfiguration wie Production.

---

### 3.7 LiveKit Egress Config

#### `livekit-egress.yaml`

Geändert:

- `api_key` entfernt.
- `api_secret` entfernt.
- `ws_url` entfernt.
- `insecure: true` bleibt erhalten.

Egress nutzt jetzt Environment:

- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `LIVEKIT_WS_URL`

Ziel:

- keine hardcoded LiveKit-Secrets in Egress-Config.

#### `livekit-egress-e2e.yaml (REMOVED from repo)`

Analog geändert.

---

### 3.8 Environment Beispiel

#### `.env.example`

Ergänzt:

```env
# LiveKit
LIVEKIT_URL=ws://livekit-server:7880
LIVEKIT_PUBLIC_URL=ws://localhost:7880
LIVEKIT_API_KEY=change-me-livekit-api-key
LIVEKIT_API_SECRET=change-me-livekit-api-secret
LIVEKIT_NODE_IP=
```

Ziel:

- dokumentieren, welche LiveKit-Variablen für Production und E2E benötigt werden.

## 4. Was erreicht wurde

### Frontend

- LiveKit Connection State wird jetzt aktiv beobachtet.
- `livekitError` wird bei erfolgreicher Verbindung gelöscht.
- Recording-Start ist nur möglich, wenn LiveKit verbunden ist.
- UI zeigt keinen permanenten alten Connection Error mehr, wenn die Verbindung später erfolgreich ist.
- PeerConnection-Timeout wurde von LiveKit-Default 15s auf 30s erhöht.
- Initiale Retry-Anzahl wurde auf 3 gesetzt.

### Backend

- LiveKit API Key/Secret werden aus Settings gelesen.
- Token-Endpoint validiert fehlende LiveKit-Konfiguration.
- Recording-Start filtert Meeting nach `client_id`.
- Webhook-Verarbeitung ist tenant-safe.
- Webhook-Logging gibt keine Authorization-Header-Teile mehr aus.

### Infrastruktur

- LiveKit Server nutzt TCP-ICE-Fallback über Port 7881.
- LiveKit Server Secrets werden zur Laufzeit eingesetzt.
- Egress Secrets werden über Environment-Variablen übergeben.
- `LIVEKIT_NODE_IP` kann browser-erreichbar gesetzt werden.

## 5. Validierung

Durchgeführt:

```bash
cd frontend
npm run lint
npm run type-check
npm run build
```

Ergebnis:

- `npm run lint`: 0 errors, bestehende warnings im Projekt.
- `npm run type-check`: passed.
- `npm run build`: passed.

Durchgeführt:

```bash
cd backend
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile app/api/v1/livekit.py app/core/config.py
```

Ergebnis:

- Syntax-Check passed.

Durchgeführt:

```bash
sh -n livekit-entrypoint.sh (REMOVED from repo)
```

Ergebnis:

- Shell-Syntax passed.

Durchgeführt:

```bash
docker compose -f docker-compose.yml config --quiet
docker compose -f docker-compose.e2e.yml config --quiet
```

Ergebnis:

- Compose-Syntax okay.
- Warnungen wegen fehlender LiveKit-Umgebungsvariablen.

Nicht erfolgreich durchgeführt:

```bash
docker compose -f docker-compose.yml up -d
```

Ergebnis:

- Production-Stack konnte nicht vollständig starten, weil `.env` keine LiveKit-Variablen enthält.
- LiveKit Server loggte:

```txt
LIVEKIT_API_KEY and LIVEKIT_API_SECRET are required
```

Nicht durchgeführt:

```bash
docker compose -f docker-compose.e2e.yml up -d
docker compose -f docker-compose.e2e.yml exec backend pytest tests/e2e/test_livekit_integration.py -v
docker compose -f docker-compose.e2e.yml exec backend pytest tests/security/test_webhook_tenant_isolation.py -v
```

Grund:

- Production-Stack ist Blocker.
- `.env` enthält aktuell keine benötigten LiveKit-Variablen.

## 6. Benötigte Umgebungsvariablen

In `.env` müssen mindestens diese Werte gesetzt sein:

```env
LIVEKIT_URL=ws://livekit-server:7880
LIVEKIT_PUBLIC_URL=ws://localhost:7880
LIVEKIT_API_KEY=<livekit-api-key>
LIVEKIT_API_SECRET=<livekit-api-secret>
LIVEKIT_NODE_IP=
```

Für produktionsnahe oder öffentliche Deployments:

- `LIVEKIT_PUBLIC_URL` sollte die browser-erreichbare URL sein, z. B. `wss://livekit.example.com`.
- `LIVEKIT_NODE_IP` sollte gesetzt werden, wenn der automatisch erkannte Container-IP nicht browser-erreichbar ist.

## 7. Nächster geplanter Ablauf

Sobald `.env` die LiveKit-Variablen enthält:

```bash
docker compose -f docker-compose.yml up -d
docker compose -f docker-compose.e2e.yml up -d
docker compose -f docker-compose.e2e.yml exec backend pytest tests/e2e/test_livekit_integration.py -v
docker compose -f docker-compose.e2e.yml exec backend pytest tests/security/test_webhook_tenant_isolation.py -v
```

Zusätzlich manuell prüfen:

- Browser DevTools / WebRTC Internals:
  - PeerConnection wird `connected`,
  - ICE candidate pairs werden valid/writable,
  - kein dauerhafter `could not establish pc connection`.
- LiveKit Server Logs:
  - `participant_joined` für Browser-Teilnehmer,
  - kein `participant_connection_aborted`,
  - keine IPv6-/UDP-/TCP-Fehler mehr.
- Egress Logs:
  - `egress_started`,
  - `egress_ended`,
  - `egress_completed`.

## 8. Rückgängig machen

Es wurde kein Git verwendet. Rückgängig machen bedeutet daher manuelles Zurücksetzen der geänderten Dateien.

### 8.1 Dateien mit Backup

Für diese Dateien existieren lokale Backup-Dateien:

```bash
cp livekit.yaml.backup-2026-06-06 livekit.yaml
cp livekit-egress.yaml.backup-2026-06-06 livekit-egress.yaml
cp docker-compose.yml.backup-2026-06-06 docker-compose.yml
```

Damit werden diese Dateien auf den vorherigen Stand zurückgesetzt.

### 8.2 Dateien ohne Backup

Diese Dateien wurden manuell geändert und haben kein Backup im Repository:

- `frontend/src/components/meetings/MeetingRoom.tsx`
- `backend/app/api/v1/livekit.py`
- `backend/app/core/config.py`
- `livekit-e2e.yaml (REMOVED from repo)`
- `livekit-egress-e2e.yaml (REMOVED from repo)`
- `docker-compose.e2e.yml`
- `livekit-entrypoint.sh (REMOVED from repo)`
- `.env.example`

Für diese Dateien muss manuell rückgängig gemacht werden.

### 8.3 Minimaler Frontend-Rollback

In `frontend/src/components/meetings/MeetingRoom.tsx` rückgängig machen:

1. Import entfernen:
   - `useConnectionState`
   - `ConnectionState`
2. Helper-Komponente entfernen:
   - `LiveKitConnectionBridge`
3. States entfernen:
   - `livekitConnectionState`
   - `livekitConnected`
4. Callback entfernen:
   - `handleLiveKitConnectionState`
5. `useEffect` entfernen, der `livekitConnected` und `livekitError` synchronisiert.
6. In `LiveKitRoom` entfernen:
   - `connectOptions`
   - `onDisconnected`
   - `<LiveKitConnectionBridge ... />`
7. Recording-Buttons wieder wie vorher freigeben:
   - Start-Button nicht mehr von `livekitConnected` abhängig machen,
   - unterer Recording-Toggle wieder bei `recordingStatus === "idle"` anzeigen.

### 8.4 Backend-Rollback

In `backend/app/api/v1/livekit.py` rückgängig machen:

1. Hardcodierte Konstanten wiederherstellen:
   - `_LIVEKIT_API_KEY = "meeting-api-key"`
   - `_LIVEKIT_API_SECRET = "meeting-api-secret-2026"`
2. `WebhookReceiver` wieder mit diesen Konstanten initialisieren.
3. Validierung in `get_livekit_token()` entfernen.
4. `start_livekit_recording()` wieder auf `db.get(Meeting, meeting_id)` setzen.
5. Webhook-Lookups wieder ohne `Meeting.client_id`-Join verwenden.
6. `_get_meeting_client_id()` entfernen.
7. `_get_active_recording_for_meeting()` entfernen.
8. `_mark_recording_failed()` wieder ohne tenant-safe Lookup verwenden.

In `backend/app/core/config.py` rückgängig machen:

```python
LIVEKIT_URL: str = "ws://livekit-server:7880"
LIVEKIT_PUBLIC_URL: str = "ws://localhost:7880"
LIVEKIT_API_KEY: str = "meeting-api-key"
LIVEKIT_API_SECRET: str = "meeting-api-secret-2026"
```

### 8.5 LiveKit Config Rollback

`livekit.yaml` manuell zurücksetzen:

- `rtc.tcp_port: 7881` entfernen.
- `keys` wieder hardcoded setzen:

```yaml
keys:
  meeting-api-key: meeting-api-secret-2026
```

- `webhook.api_key` wieder hardcoded setzen:

```yaml
webhook:
  api_key: meeting-api-key
```

`livekit-e2e.yaml (REMOVED from repo)` manuell zurücksetzen:

- `rtc.tcp_port: 7881` entfernen.
- `keys` wieder hardcoded setzen.
- `webhook.api_key` wieder hardcoded setzen.

`livekit-entrypoint.sh (REMOVED from repo)` manuell zurücksetzen:

- Env-Prüfung entfernen.
- `escape_sed_replacement()` entfernen.
- `NODE_IP` wieder per `hostname -i` setzen.
- keine `/tmp/livekit.yaml`-Generierung mehr.
- LiveKit Server wieder mit `/etc/livekit.yaml` starten.

`livekit-egress.yaml` und `livekit-egress-e2e.yaml (REMOVED from repo)` manuell zurücksetzen:

```yaml
log_level: debug
api_key: meeting-api-key
api_secret: meeting-api-secret-2026
ws_url: ws://livekit-server:7880
insecure: true
```

### 8.6 Docker Compose Rollback

`docker-compose.yml` manuell zurücksetzen:

- Backend wieder mit hardcoded LiveKit-Werten setzen:
  - `LIVEKIT_URL=ws://livekit-server:7880`
  - `LIVEKIT_PUBLIC_URL=ws://localhost:7880`
  - `LIVEKIT_API_KEY=meeting-api-key`
  - `LIVEKIT_API_SECRET=meeting-api-secret-2026`
- `livekit-server` Environment entfernen.
- `"7881:7881/tcp"` entfernen.
- `livekit-egress` Environment entfernen:
  - `LIVEKIT_API_KEY`
  - `LIVEKIT_API_SECRET`
  - `LIVEKIT_WS_URL`

`docker-compose.e2e.yml` manuell zurücksetzen:

- Backend wieder mit hardcoded LiveKit-Werten setzen.
- `livekit-server` Environment entfernen.
- `"7881:7881/tcp"` entfernen.
- `livekit-egress` Environment entfernen.

### 8.7 `.env.example` Rollback

In `.env.example` den LiveKit-Block entfernen:

```env
# LiveKit
LIVEKIT_URL=ws://livekit-server:7880
LIVEKIT_PUBLIC_URL=ws://localhost:7880
LIVEKIT_API_KEY=change-me-livekit-api-key
LIVEKIT_API_SECRET=change-me-livekit-api-secret
LIVEKIT_NODE_IP=
```

## 9. Aktueller Status

Erreicht:

- Frontend-Code ist gebaut und type-checked.
- Backend-Code ist syntaxgeprüft.
- Compose-Dateien sind syntaktisch validiert.
- LiveKit-Eintrittspunkt ist shell-syntaktisch validiert.
- Hardcoded LiveKit-Secrets wurden aus aktiven Production/E2E-Config-Dateien entfernt.
- Tenant-safe Webhook-Logik wurde implementiert.
- Recording-Start ist jetzt an LiveKit-Connection gebunden.

Blocker:

- `.env` enthält keine LiveKit-Umgebungsvariablen.
- Production-Stack kann deshalb nicht vollständig starten.
- E2E-Stack und E2E-Tests konnten deshalb noch nicht ausgeführt werden.

Empfohlener nächster Schritt:

1. LiveKit-Variablen lokal in `.env` setzen.
2. Production-Stack starten.
3. E2E-Stack starten.
4. LiveKit-Integrationstests ausführen.
5. Webhook-Tenant-Isolation-Tests ausführen.
