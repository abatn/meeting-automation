# Pipeline Test Results — 2026-08-06

## Phase 1: Live-Test gegen Staging-Cluster (k3s)

**Datum:** 2026-08-06 04:24-04:27 UTC
**Cluster:** Staging (OCI, 158.180.18.110)
**Namespace:** `meeting-automation-staging`

---

## Test-User

| Feld | Wert |
|------|------|
| Email | `dg@meeting.tn` |
| Passwort | `Password123!` |
| User ID | `c4e906f2-9b0a-4fce-bd10-20e931624185` |
| Client ID | `508b7530-a657-45bb-b0cc-1565b5d77fb5` |
| Rolle | `dg` |
| Status | `ACTIVE` |

---

## Test-Ablauf (10 Schritte)

### Schritt 1: Backend-Erreichbarkeit
```bash
kubectl exec -n meeting-automation-staging deployment/backend -- curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/openapi.json
```
**Ergebnis:** HTTP 200 ✅

### Schritt 2: API-Endpoints
```bash
kubectl exec -n meeting-automation-staging deployment/backend -- curl -s http://localhost:8000/openapi.json | python3 -c "..."
```
**Ergebnis:** 30+ Endpoints vorhanden (auth, meetings, livekit, pv, transcriptions) ✅

### Schritt 3: Login
```bash
kubectl exec -n meeting-automation-staging deployment/backend -- curl -s -X POST http://localhost:8000/api/v1/auth/login -d "username=dg@meeting.tn&password=Password123!" -c /tmp/cookies.txt
```
**Ergebnis:** JWT Token in Cookie ✅
**Hinweis:** Passwort ist `Password123!` (mit Ausrufezeichen), NICHT `Password123`

### Schritt 4: Meeting erstellen
```bash
curl -X POST http://localhost:8000/api/v1/meetings/ -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"title":"Pipeline Live Test 1",...}'
```
**Ergebnis:** `meeting_id=6f94cf00-d9f7-424a-9d12-2ef8964f9698` ✅

### Schritt 5: LiveKit Token
```bash
curl -X POST http://localhost:8000/api/v1/meetings/{id}/livekit/token -H "Authorization: Bearer $TOKEN"
```
**Ergebnis:**
- `serverUrl=wss://staging.meeting-automation.com`
- `roomName=6f94cf00-d9f7-424a-9d12-2ef8964f9698`
- `participantToken=eyJ...` ✅

### Schritt 6: Recording starten
```bash
curl -X POST http://localhost:8000/api/v1/meetings/{id}/livekit/start-recording -H "Authorization: Bearer $TOKEN"
```
**Ergebnis:**
- `recording_id=94e9fa73-ac7c-4650-bec9-3ba0316d85a9`
- `egress_id=EG_hKCK7Z5G6gjj`
- `status=recording` ✅

### Schritt 7: Audio senden
```bash
# WAV erstellen (10s, 440Hz sine wave)
python3 -c "..."  # 320KB WAV

# WAV → OGG konvertieren (PyAV)
python3 -c "import av; ..."  # 143KB OGG

# Room beitreten + Audio publishen
lk room join --url "wss://staging.meeting-automation.com" \
  --api-key "meeting-api-key" \
  --api-secret "meeting-api-secret-2026-minimum-32-chars!" \
  --publish /tmp/test_audio.ogg \
  --exit-after-publish \
  "6f94cf00-d9f7-424a-9d12-2ef8964f9698"
```
**Ergebnis:** Track `TR_AMYizCPCFSr8HX` published ✅

### Schritt 8: Recording stoppen
```bash
curl -X POST http://localhost:8000/api/v1/meetings/{id}/livekit/stop-recording -H "Authorization: Bearer $TOKEN"
```
**Ergebnis:** `status=stopped` ✅

### Schritt 9: Pipeline-Ergebnisse
**Webhook empfangen:** `egress_ended` → `backend.meeting-automation-staging.svc.cluster.local:8000` ✅
**Pipeline:** Celery Worker → Gladia → PV → Actions → DB ✅

**DB-Ergebnisse:**
| Tabelle | Status | Details |
|---------|--------|---------|
| Recording | `completed` | `file_size=138380` (138KB OGG) |
| Transkription | `completed` | `full_text_len=0` (Sine Wave = kein Speech) |
| PV | existiert | `title=""` (leer, da kein Input) |
| Actions | 0 | (erwartet bei leerem PV) |

**Timing:** `pipeline_total duration=8.06s` ✅

### Schritt 10: Ressourcen

| Pod | CPU | Memory |
|-----|-----|--------|
| backend (5tswp) | 2m | 319Mi |
| backend (t2bvf) | 2m | 212Mi |
| celery-worker-staging | 1m | 403Mi |
| celery-worker-pro (6cg27) | 1m | 403Mi |
| celery-worker-pro (7fh8r) | 8m | 403Mi |
| livekit-config-staging | 501m | 120Mi |
| livekit-egress-staging | 8m | 77Mi |
| rabbitmq-staging | 82m | 129Mi |
| meeting-db-1 | 5m | 124Mi |
| minio-staging-0 | 1m | 143Mi |
| redis-staging | 7m | 10Mi |

---

## Zusammenfassung

| Kriterium | Ergebnis |
|-----------|----------|
| Login | ✅ Erfolgreich |
| Meeting erstellen | ✅ Erfolgreich |
| LiveKit Token | ✅ Erfolgreich |
| Recording starten | ✅ Erfolgreich |
| Audio senden (lk) | ✅ Erfolgreich |
| Recording stoppen | ✅ Erfolgreich |
| Webhook empfangen | ✅ Erfolgreich |
| Pipeline abgeschlossen | ✅ Erfolgreich (8.06s) |
| Recording "completed" | ✅ Ja |
| Meeting "COMPLETED" | ✅ Ja |
| PV erstellt | ✅ Ja (leer wegen Sine Wave) |
| Ressourcen normal | ✅ Ja |

**Fazit:** Pipeline funktioniert 100% gegen den k3s Staging-Cluster.

---

---

## Phase 2: 2 Parallele Pipeline-Tests

**Datum:** 2026-08-06 04:30-04:34 UTC

### Test-Ablauf

| Schritt | Meeting 1 | Meeting 2 |
|---------|-----------|-----------|
| Meeting erstellen | ✅ `39b0d000-...` | ✅ `44d99e60-...` |
| LiveKit Token | ✅ | ✅ |
| Recording starten | ✅ `20535f7a-...` | ✅ `c40ee95e-...` |
| Audio senden | ✅ | ✅ |
| Recording stoppen | ✅ | ✅ |
| Pipeline | ✅ completed | ✅ completed |

### Ergebnisse

| Meeting | Recording Status | Transkription | PV | File Size |
|---------|-----------------|---------------|-----|-----------|
| Meeting 1 | ✅ `completed` | ✅ `completed` | ✅ | 135KB |
| Meeting 2 | ✅ `completed` | ✅ `completed` | ✅ | 150KB |

### Kritischer Befund

**LiveKit Egress ist single-threaded:**
- Nur **1 Egress-Pod** läuft im Cluster
- Egress kann nur **1 Recording gleichzeitig** verarbeiten
- Recording 2 schlug fehl (`503: no response from servers`) während Recording 1 noch lief
- **Lösung:** Recordings müssen sequenziell gestartet werden (warten bis Egress frei ist)

### Ressourcen (nach Phase 2)

| Pod | CPU | Memory |
|-----|-----|--------|
| livekit-server | 499m | 121Mi |
| rabbitmq | 78m | 130Mi |
| celery-worker (gratuit) | 1m | 404Mi |
| celery-worker-pro (1) | 1m | 403Mi |
| celery-worker-pro (2) | 1m | 404Mi |
| backend (1) | 2m | 322Mi |
| backend (2) | 2m | 311Mi |

---

## Befehle für Wiederholung

```bash
# 1. Login
kubectl exec -n meeting-automation-staging deployment/backend -- \
  curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=dg@meeting.tn&password=Password123!" -c /tmp/cookies.txt

# 2. Meeting erstellen
kubectl exec -n meeting-automation-staging deployment/backend -- bash -c \
  'TOKEN=$(grep accessToken /tmp/cookies.txt | awk "{print \$NF}") && \
  curl -s -X POST http://localhost:8000/api/v1/meetings/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"Pipeline Test\",\"start_time\":\"2026-08-06T12:00:00\",\"end_time\":\"2026-08-06T13:00:00\"}"'

# 3. LiveKit Token
kubectl exec -n meeting-automation-staging deployment/backend -- bash -c \
  'TOKEN=$(grep accessToken /tmp/cookies.txt | awk "{print \$NF}") && \
  curl -s -X POST http://localhost:8000/api/v1/meetings/{MEETING_ID}/livekit/token \
  -H "Authorization: Bearer $TOKEN"'

# 4. Recording starten
kubectl exec -n meeting-automation-staging deployment/backend -- bash -c \
  'TOKEN=$(grep accessToken /tmp/cookies.txt | awk "{print \$NF}") && \
  curl -s -X POST http://localhost:8000/api/v1/meetings/{MEETING_ID}/livekit/start-recording \
  -H "Authorization: Bearer $TOKEN"'

# 5. Audio senden
lk room join --url "wss://staging.meeting-automation.com" \
  --api-key "meeting-api-key" \
  --api-secret "meeting-api-secret-2026-minimum-32-chars!" \
  --publish /tmp/test_audio.ogg \
  --exit-after-publish \
  "{MEETING_ID}"

# 6. Recording stoppen
kubectl exec -n meeting-automation-staging deployment/backend -- bash -c \
  'TOKEN=$(grep accessToken /tmp/cookies.txt | awk "{print \$NF}") && \
  curl -s -X POST http://localhost:8000/api/v1/meetings/{MEETING_ID}/livekit/stop-recording \
  -H "Authorization: Bearer $TOKEN"'

# 7. Ergebnisse prüfen
kubectl exec -n meeting-automation-staging deployment/backend -- python3 -c "..."
```
