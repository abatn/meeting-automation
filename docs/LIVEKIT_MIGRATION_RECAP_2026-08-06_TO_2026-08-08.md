# LiveKit Migration Recap — 06.08 bis 08.08.2026

**Erstellt:** 2026-08-08 | **Zeitraum:** 06.08.2026 – 08.08.2026  
**Aktualisiert:** 2026-08-08 (Service-Selector-Fix 9.6, CPU-Reduktion 9.7)  
**Ziel:** Migration von MediaRecorder auf LiveKit SFU für Echtzeit-Audio + automatische Recording-Pipeline  
**Cluster:** k3s single-node (OCI, ARM64, `158.180.18.110`)  
**Namespace:** `meeting-automation-staging`

---

## Inhaltsverzeichnis

1. [Zeitplan & Übersicht](#1-zeitplan--übersicht)
2. [Architektur](#2-architektur)
3. [LiveKit Server — Helm & Konfiguration](#3-livekit-server--helm--konfiguration)
4. [LiveKit Egress — Helm & Konfiguration](#4-livekit-egress--helm--konfiguration)
5. [Backend-Integration](#5-backend-integration)
6. [Frontend-Integration & SDK-Patches](#6-frontend-integration--sdk-patches)
7. [Network Policies](#7-network-policies)
8. [Recording-Pipeline (E2E)](#8-recording-pipeline-e2e)
9. [Gefundene Probleme & Fixes (chronologisch)](#9-gefundene-probleme--fixes-chronologisch)
10. [Verifizierter Endzustand](#10-verifizierter-endzustand)
11. [Datei-Referenz](#11-datei-referenz)
12. [Lessons Learned](#12-lessons-learned)

---

## 1. Zeitplan & Übersicht

| Datum | Meilenstein | Ergebnis |
|-------|-------------|----------|
| **06.08** | LiveKit Server + Egress in k3s deployen | Server läuft, EGRESS_ABORTED nach 10s |
| **06.08** | Pipeline-Test-Plan erstellt | Test-User Login + Meeting-Erstellung erfolgreich |
| **06.08** | Recording Start Guard Fix | Guard eingeführt: Egress erst nach Audio-Publikation |
| **07.08** | 15s Disconnect Root Cause Analysis | SDK-Timeout (peerConnectionTimeout: 15s) identifiziert |
| **07.08** | TURN/ICE Deep Dive | TURN-TLS, UDP-Relay, ICE-Transport-Policy analysiert |
| **07.08** | MeetingRoom Code-Analyse | LiveKit-Integration in MeetingRoom.tsx evaluiert |
| **07.08** | Network Analysis | Calico, kube-proxy, hostNetwork-Routing analysiert |
| **08.08** | SDK-Patch (Option B) | `livekit-client` ESM-Bundle gepatcht: id-0-Antworten + 60s-Timeouts |
| **08.08** | MeetingRoom.tsx Type-Fix | `onReconnecting`/`onReconnected` Props entfernt, Reconnect-State via `useConnectionState` |
| **08.08** | Frontend Deploy (gepatchter SDK) | Bundle `index-CKEaWQJu.js` → `index-eY8oRDf5.js` deployed |
| **08.08** | NetworkPolicy-Fix (Helm-Labels) | `livekit-policy` + `livekit-egress-policy` mit `app.kubernetes.io/name` ergänzt |
| **08.08** | Egress Audio-Only Fix (Doku-konform) | `layout` + `preset` aus `start_egress()` entfernt (offizielle LiveKit-Doku) |
| **08.08** | **hostNetwork-Fix (ROOT CAUSE)** | Egress-Pod `hostNetwork: true` gesetzt → **Verbindung funktioniert** |
| **08.08** | **E2E-Test ERFOLGREICH** | Recording `EG_MkjjEbtExSej` → Status `completed`, Transkription erstellt |
| **08.08** | **Service-Selector-Fix** | Service `livekit-server-staging` hatte 0 Endpoints (altes `app:`-Label) → JSON-Patch auf Helm-Labels |
| **08.08** | CPU-Reduktion | LiveKit Server Limit `2000m → 1000m` (tatsächliche Nutzung nur ~1m) |

---

## 2. Architektur

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BROWSER (Firefox/Chrome)                     │
│                                                                     │
│  livekit-client JS SDK 2.19.1 (gepatcht)                          │
│  ↕ WebSocket (wss://staging.meeting-automation.com/rtc)           │
│  ↕ WebRTC (UDP 50000-60000)                                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                    LIVEKIT SERVER (hostNetwork: true)                │
│                                                                     │
│  livekit/livekit-server:latest (v1.9.0)                            │
│  Port 7880: HTTP/WS Signalisierung                                 │
│  Port 7881: TCP (RTC Fallback)                                     │
│  Port 3478: TURN/UDP (deaktiviert)                                 │
│  Port 50000-60000: WebRTC Media                                    │
│                                                                     │
│  Redis: redis-staging:6379 (Room-State)                            │
│  Webhook: → backend:8000/api/v1/livekit/webhooks                   │
└───────────┬───────────────────────────────────────┬─────────────────┘
            │                                       │
┌───────────▼───────────────┐     ┌─────────────────▼─────────────────┐
│     LIVEKIT EGRESS        │     │          BACKEND (FastAPI)         │
│  (hostNetwork: true)      │     │                                   │
│                           │     │  livekit_service.py:              │
│  livekit/egress:v1.8.4    │     │    - create_room()               │
│  Chrome → Audio Composite │     │    - generate_token()            │
│  → OGG File               │     │    - start_egress()              │
│  → MinIO S3 Upload        │     │                                   │
│                           │     │  livekit.py (API + Webhooks):     │
│  Redis: redis-staging     │     │    - /livekit/token               │
│  S3: minio-staging:9000   │     │    - /livekit/webhooks            │
│  Template: localhost:7980 │     │    - Webhook-Dedup via Redis      │
└───────────────────────────┘     └───────────────┬─────────────────┘
                                                  │
                                    ┌─────────────▼─────────────────┐
                                    │      CELERY WORKER            │
                                    │                               │
                                    │  transcription_tasks.py:      │
                                    │    process_recording()        │
                                    │    → Gladia V2 Transcription  │
                                    │    → Speaker Identification   │
                                    │    → Mistral PV Generation    │
                                    │    → Action Assignment        │
                                    │    → DB + Audit               │
                                    └───────────────────────────────┘
```

---

## 3. LiveKit Server — Helm & Konfiguration

### 3.1 Deployment (`livekit-server-deployment.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: livekit-server-staging
  namespace: meeting-automation-staging
spec:
  replicas: 1
  strategy:
    type: Recreate  # hostNetwork erfordert Recreate
  template:
    spec:
      hostNetwork: true                    # KRITISCH für single-node
      dnsPolicy: ClusterFirstWithHostNet
      nodeSelector:
        kubernetes.io/hostname: instance-20260329-0846
      containers:
      - name: livekit-server
        image: livekit/livekit-server:latest
        args: ["--config", "/etc/livekit.yaml"]
        ports:
        - containerPort: 7880              # HTTP/WS Signalisierung
        - containerPort: 7881              # TCP RTC Fallback
        - containerPort: 3478              # TURN/UDP
          protocol: UDP
        - containerPort: 50000             # WebRTC Media
          protocol: UDP
          endPort: 60000
        resources:
          requests: { cpu: 500m, memory: 512Mi }
          limits:   { cpu: 1000m, memory: 1024Mi }  # seit 2026-08-08: 1000m (Nutzung ~1m)
        livenessProbe:
          httpGet: { path: /, port: 7880 }
        readinessProbe:
          httpGet: { path: /, port: 7880 }
```

### 3.2 Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: livekit-server-staging
spec:
  type: ClusterIP
  # ⚠️ Selector MUSS die Helm-Labels enthalten (app.kubernetes.io/name + instance).
  # Ein altes `app: livekit-server-staging`-Label im Selector → 0 Endpoints (siehe 9.6).
  selector:
    app.kubernetes.io/name: livekit-server-staging
    app.kubernetes.io/instance: livekit-server
  ports:
  - name: http
    port: 7880
    targetPort: 7880
  - name: tcp
    port: 7881
    targetPort: 7881
```

### 3.3 ConfigMap (`livekit-configmap.yaml`)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: livekit-config-staging
data:
  livekit.yaml: |
    port: 7880
    log_level: info
    room:
      empty_timeout: 600
      departure_timeout: 60
      max_participants: 10
    rtc:
      tcp_port: 7881
      port_range_start: 50000
      port_range_end: 60000
      use_external_ip: true
      allow_tcp_fallback: true
      ping_interval: 5
    redis:
      address: redis-staging.meeting-automation-staging.svc.cluster.local:6379
      password: redis_password
      db: 0
    keys:
      meeting-api-key: meeting-api-secret-2026-minimum-32-chars!
    webhooks:
      url: http://backend.meeting-automation-staging.svc.cluster.local:8000/api/v1/livekit/webhooks
      api_key: meeting-api-key
      secret: meeting-api-secret-2026-minimum-32-chars!
```

### 3.4 Helm Values (`livekit-server-values.yaml`)

```yaml
replicaCount: 1
nameOverride: livekit-server-staging
fullnameOverride: livekit-server-staging

podHostNetwork: true
deploymentStrategy:
  type: Recreate

turn:
  enabled: false    # Kein TURN-TLS-Zertifikat → 403-Fehler

nodeSelector:
  kubernetes.io/hostname: instance-20260329-0846

resources:
  limits:
    cpu: 1000m   # 2026-08-08: von 2000m auf 1000m reduziert (Nutzung ~1m, 1 Teilnehmer audio-only)
    memory: 1024Mi
  requests:
    cpu: 500m
    memory: 512Mi
```

### 3.5 Secrets (`livekit-secrets.yaml`)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: livekit-secrets-staging
type: Opaque
stringData:
  LIVEKIT_API_KEY: meeting-api-key
  LIVEKIT_API_SECRET: meeting-api-secret-2026-minimum-32-chars!
```

---

## 4. LiveKit Egress — Helm & Konfiguration

### 4.1 Deployment (Helm-managed: `livekit-egress`)

**WICHTIG:** Das Helm-Chart managed das Deployment `livekit-egress` (NICHT `livekit-egress-staging`). Die lokale YAML `livekit-egress-deployment.yaml` ist NICHT die aktive Quelle.

```yaml
# Laufendes Deployment (nach kubectl patch):
spec:
  replicas: 1
  strategy:
    type: Recreate
  template:
    spec:
      hostNetwork: true                    # KRITISCH — per kubectl patch gesetzt
      dnsPolicy: ClusterFirstWithHostNet   # KRITISCH — per kubectl patch gesetzt
      containers:
      - name: egress
        image: livekit/egress:v1.8.4
        env:
        - name: EGRESS_CONFIG_BODY
          valueFrom:
            configMapKeyRef:
              name: livekit-egress-config-staging
              key: config.yaml
        ports:
        - containerPort: 7000              # Health
        resources:
          requests: { cpu: 200m, memory: 512Mi }
          limits:   { cpu: "1", memory: 2Gi }
```

### 4.2 ConfigMap (`livekit-egress-configmap.yaml`)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: livekit-egress-config-staging
data:
  config.yaml: |
    log_level: debug
    insecure: true
    redis:
      address: redis-staging.meeting-automation-staging.svc.cluster.local:6379
      password: redis_password
      db: 0
    s3:
      access_key: minio_user
      secret: minio_password
      endpoint: http://minio-staging:9000
      bucket: meeting-recordings-staging
      region: us-east-1
      force_path_style: true
    health_port: 7000
    template_port: 7980
    prometheus_port: 7002
    cpu_cost:
      room_composite_cpu_cost: 1.5
      web_cpu_cost: 1.5
      track_composite_cpu_cost: 1.0
      track_cpu_cost: 0.5
```

### 4.3 Helm Values (`egress-values.yaml`)

```yaml
replicaCount: 1
image:
  repository: livekit/egress
  pullPolicy: IfNotPresent

egress:
  log_level: debug
  insecure: true
  ws_url: ws://livekit-server-staging:7880
  api_key: meeting-api-key
  api_secret: meeting-api-secret-2026-minimum-32-chars!
  redis:
    address: redis-staging.meeting-automation-staging.svc.cluster.local:6379
    password: redis_password
    db: 0
  s3:
    access_key: minio_user
    secret: minio_password
    endpoint: http://minio-staging:9000
    bucket: meeting-recordings-staging
    region: us-east-1
    force_path_style: true
  health_port: 7000
  template_port: 7980
  prometheus_port: 7002
  cpu_cost:
    room_composite_cpu_cost: 1.5
    web_cpu_cost: 1.5
    track_composite_cpu_cost: 1.0
    track_cpu_cost: 0.5

resources:
  limits:
    cpu: "1"
    memory: 2Gi
  requests:
    cpu: 200m
    memory: 512Mi

terminationGracePeriodSeconds: 3600
deploymentStrategy:
  type: Recreate

# CRITICAL: hostNetwork (2026-08-12)
# Das Helm-Chart rendert hostNetwork NICHT aus Values.
# Muss nach jedem helm upgrade manuell gesetzt werden:
#   kubectl patch deployment livekit-egress -n meeting-automation-staging \
#     --type='json' \
#     -p='[{"op":"add","path":"/spec/template/spec/hostNetwork","value":true},{"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"}]'
hostNetwork: true  # Referenz — manuell per kubectl patch
```

### 4.4 hostNetwork Patch (nach jedem Helm-Upgrade ausführen)

```bash
kubectl patch deployment livekit-egress -n meeting-automation-staging --type='json' \
  -p='[
    {"op":"add","path":"/spec/template/spec/hostNetwork","value":true},
    {"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"}
  ]'
kubectl rollout restart deployment/livekit-egress -n meeting-automation-staging
```

---

## 5. Backend-Integration

### 5.1 `livekit_service.py` — LiveKit API Client

```python
class LiveKitService:
    """LiveKit Server API Integration."""

    def __init__(self):
        self.api = LiveKitAPI(
            url=settings.LIVEKIT_URL,          # ws://livekit-server-staging:7880
            api_key=settings.LIVEKIT_API_KEY,  # meeting-api-key
            api_secret=settings.LIVEKIT_API_SECRET,
        )

    async def create_room(self, meeting_id: str):
        """Room bei Meeting-Erstellung erstellen."""
        await self.api.room.create_room(
            name=meeting_id,
            empty_timeout=300,
            max_participants=50,
        )

    async def generate_token(self, meeting_id: str, user_id: str) -> str:
        """JWT-Token für Frontend-Verbindung generieren."""
        token = AccessToken(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        token.identity = f"{user_id}_{secrets.token_hex(4)}"
        token.add_grant(VideoGrants(
            room_join=True,
            room=meeting_id,
            can_publish=True,
            can_subscribe=True,
        ))
        return token.to_jwt()

    async def start_egress(self, meeting_id: str, recording_id: str) -> str:
        """Recording starten — AUDIO ONLY (kein layout, kein preset)."""
        file_output = EncodedFileOutput()
        file_output.filepath = f"{meeting_id}/recordings/{recording_id}_livekit.ogg"
        file_output.disable_manifest = True

        req = RoomCompositeEgressRequest()
        req.room_name = meeting_id
        # Kein layout → Audio-Pipeline (offizielle LiveKit-Doku):
        # "Don't set layout or custom_base_url as these parameters
        #  force the recording through the video pipeline."
        req.audio_only = True
        req.file.CopyFrom(file_output)

        info = await self.api.egress.start_room_composite_egress(req)
        return info.egress_id
```

### 5.2 `livekit.py` — API-Endpoints + Webhook

```python
router = APIRouter()

@router.post("/meetings/{meeting_id}/livekit/token")
async def get_livekit_token(meeting_id: str, user=Depends(get_current_user)):
    """LiveKit-Verbindungstoken generieren."""
    service = LiveKitService()
    token = await service.generate_token(meeting_id, str(user.id))
    return {"token": token, "server_url": settings.LIVEKIT_URL}

@router.post("/livekit/webhooks")
async def livekit_webhook(request: Request):
    """Egress-Webhook empfangen → Recording-Pipeline starten."""
    # Webhook-Deduplication via Redis (SETNX, 24h TTL)
    event_id = await _claim_webhook_event(data)
    if not event_id:
        return {"ok": True, "duplicate": True}

    # Recording-Status aktualisieren + Pipeline triggern
    if data.get("event") == "egress.completed":
        process_recording.delay(recording_id, client_id=client_id)
    return {"ok": True}
```

---

## 6. Frontend-Integration & SDK-Patches

### 6.1 SDK-Patch (Option B) — `livekit-client` ESM Bundle

**Root Cause:** `livekit-server v1.9.0` gibt in Antworten keine Offer-IDs zurück (`id = 0`). Das Standardverhalten von `PCTransportManager.negotiate()` löscht sein 15s-Timeout nur bei `OfferAnswered(offerId > checkpoint)` — aber `checkpoint >= 1`, also nie bei `id = 0`.

**Patch-Dateien:**

| Datei | Zweck |
|-------|-------|
| `frontend/patches/patch-livekit-client.py` | Reproduzierbares Skript: kopiert ESM-Bundle, ersetzt `onAnswered`-Block byte-exakt |
| `frontend/patches/livekit-client.esm.mjs` | Gepatchtes Bundle (@2.19.1) mit `offerId > checkpoint \|\| offerId === 0` |
| `frontend/patches/check-livekit-patch.mjs` | Pre-Build-Guard: prüft Versions-Match + Fix-Marker |
| `frontend/patches/README.md` | Dokumentation: Rationale, Regeneration, Verification |

**Änderung im Bundle:**
```
ALT:  if (offerId > checkpoint) { clearDeadline(); startNext(); }
NEU:  if (offerId > checkpoint || offerId === 0) { clearDeadline(); startNext(); }
```

**Zusätzlich:** Alle hardcoded 15s-SDK-Timeouts (`peerConnectionTimeout`, `websocketTimeout`, etc.) auf `60000ms` (60s) erhöht.

### 6.2 Vite-Alias (`vite.config.ts`)

```typescript
import { fileURLToPath, URL } from 'node:url'

const livekitPatchedEntry = fileURLToPath(
  new URL('./patches/livekit-client.esm.mjs', import.meta.url),
)

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      { find: /^livekit-client$/, replacement: livekitPatchedEntry },
    ],
  },
})
```

### 6.3 Pre-Build Guard (`package.json`)

```json
{
  "scripts": {
    "prebuild": "node patches/check-livekit-patch.mjs",
    "build": "vite build"
  }
}
```

### 6.4 MeetingRoom.tsx — LiveKit-Integration

**Key Components:**
- `LiveKitRoom` — Hauptverbindungskomponente
- `RoomAudioRenderer` — Audio für alle Teilnehmer
- `useConnectionState` — Verbindungsstatus-Tracking
- `LiveKitConnectionBridge` — Zustandsbrücke für React-State
- `LiveKitDisconnectBridge` — Trennungssteuerung

**Reconnect-Handling (via `useConnectionState`):**

```typescript
const handleLiveKitConnectionState = useCallback((state: ConnectionState) => {
  const connected = state === ConnectionState.Connected;
  const reconnecting =
    state === ConnectionState.Reconnecting ||
    state === ConnectionState.SignalReconnecting;

  setLivekitConnectionState(state);
  setLivekitConnected(connected);

  if (connected) {
    setLivekitError(null);
    setRoomConnectionReady(true);
    setIsReconnecting(false);
  } else if (reconnecting) {
    console.warn("[LiveKit] Reconnecting...");
    setIsReconnecting(true);
  }
}, []);
```

---

## 7. Network Policies

### 7.1 `livekit-policy` (schützt den Server)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: livekit-policy
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: livekit-server-staging
  policyTypes: [Ingress, Egress]
  ingress:
  - from:
    - podSelector:           # Altes Label (Fallback)
        matchLabels:
          app: livekit-egress-staging
    - podSelector:           # Helm-Label (NEU 2026-08-12)
        matchLabels:
          app.kubernetes.io/name: egress
    - podSelector:
        matchLabels:
          app: backend
    ports:
    - port: 7880
      protocol: TCP
    - port: 7881
      protocol: TCP
  - from:
    - namespaceSelector: {}
    ports:
    - port: 7881
      protocol: TCP
    - port: 3478
      protocol: UDP
  egress:
  - to:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: redis-staging
    ports:
    - port: 6379
      protocol: TCP
  - to:
    - podSelector:
        matchLabels:
          app: backend
    ports:
    - port: 8000
      protocol: TCP
  - ports:
    - port: 53
      protocol: UDP
    - port: 53
      protocol: TCP
    to:
    - namespaceSelector: {}
```

### 7.2 `livekit-egress-policy` (schützt den Egress)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: livekit-egress-policy
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: egress
  policyTypes: [Ingress, Egress]
  egress:
  - to:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: redis-staging
    ports:
    - port: 6379
      protocol: TCP
  - to:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: minio-staging
    ports:
    - port: 9000
      protocol: TCP
  - to:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: livekit-server-staging
    ports:
    - port: 7880
      protocol: TCP
  - ports:
    - port: 53
      protocol: UDP
    - port: 53
      protocol: TCP
    to:
    - namespaceSelector: {}
```

### 7.3 `default-deny-all`

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes:
  - Ingress
```

### 7.4 Wichtige NetworkPolicy-Lesungen

| Regel | Erklärung |
|-------|-----------|
| `podSelector: {}` | Matcht ALLE Pods im Namespace |
| Zwei `podSelector` in einem `from` | **OR**-Logik: Traffic wird erlaubt wenn EIN Selector matcht |
| `namespaceSelector: {}` + `podSelector` | **AND**-Logik: Beide müssen matchen |
| `policyTypes: [Ingress, Egress]` | Aktiviert both — ohne explizite Regel wird alles blockiert |
| hostNetwork-Pods | Kein veth → Calico wendet NetworkPolicy NICHT an |

---

## 8. Recording-Pipeline (E2E)

### 8.1 Flow

```
1. User klickt "Recording starten" (Frontend)
   ↓
2. POST /api/v1/recordings/start (Backend)
   ↓
3. livekit_service.start_egress(meeting_id, recording_id)
   → RoomCompositeEgressRequest (audio_only=true)
   → LiveKit Server startet Egress
   ↓
4. LiveKit Egress startet Chrome (Template localhost:7980)
   → Chrome verbindet sich mit LiveKit Server (WebSocket)
   → Subskribiert Audio-Tracks
   → Composite → OGG File
   ↓
5. Egress lädt File nach MinIO S3 hoch
   → POST webhook an backend: /api/v1/livekit/webhooks
   ↓
6. Backend empfängt Webhook (egress.completed)
   → Redis SETNX Dedup (24h TTL)
   → Recording-Status → "completed"
   → Celery Task: process_recording.delay()
   ↓
7. Celery Worker (transcription_tasks.py):
   a. File von MinIO downloaden
   b. Gladia V2: Transkription + Diarisierung
   c. Speaker Identification (ONNX 192-dim Embeddings)
   d. Display Transcript mit echten Namen an Mistral senden
   e. Mistral PV Generierung (Temperature 0.1)
   f. Action Assignment (AssigneeResolver 5-Schritte)
   g. DB speichern + Audit Log
   ↓
8. Frontend: Transkription + PV anzeigen
```

### 8.2 Timing-Instrumentation

```python
# In transcription_tasks.py:
TIMING: recording_download_duration=2.34s
TIMING: gladia_polling_duration=112.50s
TIMING: speaker_identification_duration=8.21s
TIMING: mistral_pv_duration=4.67s
TIMING: pipeline_total=142.89s
```

Extrahieren mit: `docker logs celery-worker | grep TIMING`

### 8.3 Audio-Only Egress (offizielle Doku)

```
RoomCompositeEgressRequest:
  room_name: meeting_id
  audio_only: true        # ✅ Pflicht für Audio-Only
  layout: NICHT SETZEN    # ⚠️ Erzwingt Video-Pipeline!
  custom_base_url: LEER   # ⚠️ Erzwingt Video-Pipeline!
  file: EncodedFileOutput (OGG)
```

**Offizielle Zitate (docs.livekit.io):**
- *"Don't set layout or custom_base_url as these parameters force the recording through the video pipeline."*
- *"Leave layout and custom_base_url parameters unset to preserve the audio-only billing rate."*

---

## 9. Gefundene Probleme & Fixes (chronologisch)

### 9.1 EGRESS_ABORTED: "Start signal not received" (06.08)

| Fakt | Detail |
|------|--------|
| **Symptom** | Recording bricht nach ~10s ab, `EGRESS_ABORTED` |
| **Ursache 1** | `layout="speaker"` + `preset=H264_720P_30` → Video-Pipeline statt Audio-Pipeline |
| **Fix 1** | `layout` + `preset` aus `start_egress()` entfernt (gem. offizieller Doku) |
| **Ursache 2** | NetworkPolicy: `livekit-policy` erlaubte Ingress nur von `app: livekit-egress-staging` (altes Label) |
| **Fix 2** | Helm-Label `app.kubernetes.io/name: egress` in NetworkPolicies ergänzt |
| **Ursache 3** | **hostNetwork-Mismatch**: Server `hostNetwork: true`, Egress `hostNetwork: false` → Calico/kube-proxy kann Traffic nicht routen |
| **Fix 3** | `kubectl patch` → Egress-Pod `hostNetwork: true` + `dnsPolicy: ClusterFirstWithHostNet` |

### 9.2 15s Disconnect: CLIENT_REQUEST_LEAVE (07.08)

| Fakt | Detail |
|------|--------|
| **Symptom** | Verbindung bricht nach exakt 15s ab, `CLIENT_REQUEST_LEAVE` |
| **Ursache** | `livekit-client` SDK: `PCTransportManager.negotiate()` hat hardcoded 15s-Timeout. Server v1.9.0 gibt Offer-ID 0 zurück, SDK prüft nur `offerId > checkpoint` (checkpoint >= 1) |
| **Fix** | Option B: ESM-Bundle gepatcht → `offerId > checkpoint \|\| offerId === 0` + alle 15s-Timeouts auf 60s erhöht |

### 9.3 MeetingRoom Type-Error (08.08)

| Fakt | Detail |
|------|--------|
| **Symptom** | `npm run type-check` fehlschlägt: `TS2322: onReconnecting/onReconnected` nicht in `LiveKitRoomProps` |
| **Ursache** | `@livekit/components-react@2.9.21` hat diese Props nicht — waren nie wired |
| **Fix** | Props entfernt, Reconnect-State via `useConnectionState` Bridge |

### 9.4 CPU-Underprovisionierung (08.08)

| Fakt | Detail |
|------|--------|
| **Symptom** | LiveKit Server 100% CPU, Egress-Logs: `not enough cpu for some egress types` |
| **Ursache** | CPU-Limit 500m (zu niedrig) |
| **Fix** | CPU-Limit auf 2000m erhöht |

### 9.5 TURN/ICE-Probleme (07.08)

| Fakt | Detail |
|------|--------|
| **Symptom** | Reconnect-Loops, `DUPLICATE_IDENTITY`, UDP-Verbindungen scheitern |
| **Ursache** | TURN-TLS ohne Zertifikat (403), stale ICE-Config-Cache mit `forceRelay=ENABLED`, UDP-Ports 50000-60000 blockiert |
| **Fix** | TURN deaktiviert (`turn.enabled: false`), ConfigMap bereinigt, UDP-Fallback aktiviert |

### 9.6 Service ohne Endpoints: Label-Selector-Mismatch (08.08)

| Fakt | Detail |
|------|--------|
| **Symptom** | Service `livekit-server-staging` zeigt `ENDPOINTS: <none>` seit 46h; Backend (`LIVEKIT_URL`), Egress (`ws_url`) und Ingress `/livekit` erhalten `Connection refused` |
| **Ursache** | Service-Selector verlangte `app: livekit-server-staging` — stammt aus der alten direkten YAML (`livekit-server-deployment.yaml`, per `kubectl apply`), die beim Helm-Umstieg den Helm-Service überlagert hat. Die Helm-Pods tragen aber nur `app.kubernetes.io/name` + `app.kubernetes.io/instance` → **0 Endpoints** (UND-Verknüpfung) |
| **Vorher funktioniert?** | JA — vor der Helm-Migration trugen Pod UND Service beide `app: livekit-server-staging` → konsistent. Erst der Helm-Umstieg erzeugte den Mismatch |
| **Fallstrick** | `kubectl patch --type=merge` ERGÄNZT den Selector nur (alle Labels bleiben) → wirkungslos. Erst `--type=json` mit `replace` auf `/spec/selector` ersetzt ihn komplett |
| **Fix** | `kubectl patch svc livekit-server-staging -n meeting-automation-staging --type=json -p='[{"op":"replace","path":"/spec/selector","value":{"app.kubernetes.io/name":"livekit-server-staging","app.kubernetes.io/instance":"livekit-server"}}]'` → Endpoints erscheinen sofort (`10.0.0.191:7880,7881`) |
| **Verify** | Backend → `livekit-server-staging:7880` ✅ OK (vorher `Connection refused`); EndpointSlice ready mit `targetRef` auf Running-Pod |

### 9.7 CPU-Limit-Reduktion (08.08)

| Fakt | Detail |
|------|--------|
| **Symptom** | LiveKit Server Limit 2000m (2 CPU) bei tatsächlicher Nutzung von nur ~1m CPU / 51Mi RAM (1 Teilnehmer, audio-only) |
| **Ursache** | Limit war für den realen Nutzungsumfang überdimensioniert |
| **Fix** | `kubectl patch` → `limits.cpu: 2000m → 1000m` + beide YAMLs im Repo aktualisiert |
| **Wichtig** | Per `kubectl patch` angewendet, **nicht** per `helm upgrade` (würde hostNetwork/dnsPolicy zurücksetzen); Werte in `livekit-server-values.yaml` gepflegt |
| **Verify** | Rollout erfolgreich, `limits.cpu: "1"`, hostNetwork/dnsPolicy unverändert, Server v1.9.0 läuft, HTTP OK auf 7880 |

---

## 10. Verifizierter Endzustand (08.08, 13:33 UTC)

### E2E-Test: "meeting hostnet"

| Schritt | Status | Detail |
|---------|--------|--------|
| Meeting erstellt | ✅ | `ea480422-ebf3-44bb-adec-9dca2caae26f` |
| User join (Firefox) | ✅ | Audio/opus publiziert, `participant_joined` |
| Egress-Chrome join | ✅ | **Verbindung funktioniert!** (hostNetwork-Fix) |
| Recording gestartet | ✅ | `EG_MkjjEbtExSej`, `StartRoomCompositeEgress` |
| EGRESS_ACTIVE | ✅ | Chrome nimmt Audio auf |
| EGRESS_COMPLETE | ✅ | File nach MinIO hochgeladen |
| Recording-Status | ✅ | `completed` in DB |
| Transkription | ✅ | 1 Eintrag erstellt |
| Kein abrupter Disconnect | ✅ | Kein `CLIENT_REQUEST_LEAVE` während Sessions |

### Connectivity-Tests (hostNetwork Egress-Pod)

| Test | Ziel | Ergebnis |
|------|------|----------|
| Service DNS | `livekit-server-staging:7880` | ✅ Exit-Code 0 |
| localhost | `localhost:7880` | ✅ Exit-Code 0 |
| Node-IP | `10.0.0.191:7880` | ✅ Exit-Code 0 |
| Redis | `redis-staging:6379` | ✅ TCP connect |

### Service-Selector-Fix (2026-08-08, nach Recap-Erstellung)

| Check | Vorher | Nachher |
|-------|--------|---------|
| **Endpoints** | `<none>` (46h) | ✅ `10.0.0.191:7880, 10.0.0.191:7881` |
| **Backend → Service-DNS** (`LIVEKIT_URL`, Room-API) | ❌ `Connection refused` | ✅ **OK** |
| **EndpointSlice** | leer | ✅ ready, `targetRef` auf Running-Pod |
| **Egress-Pod** | — | ✅ läuft (1/1, hostNetwork=true, kein Restart) |
| **CPU-Limit** | `2` (2000m) | ✅ `1` (1000m) |

---

## 11. Datei-Referenz

### Backend

| Datei | Änderung |
|-------|----------|
| `backend/app/services/livekit_service.py` | `start_egress()`: layout+preset entfernt (Audio-Only Doku) |
| `backend/app/api/v1/livekit.py` | Token-Endpoint + Webhook-Handler + Redis-Dedup |
| `backend/app/tasks/transcription_tasks.py` | Pipeline: Gladia → Speaker ID → Mistral PV → Actions |

### Frontend

| Datei | Änderung |
|-------|----------|
| `frontend/src/components/meetings/MeetingRoom.tsx` | LiveKit-Integration, `useConnectionState` Bridge |
| `frontend/vite.config.ts` | Regex-Alias für gepatchtes `livekit-client` |
| `frontend/package.json` | `prebuild` Guard für Patch-Verifikation |
| `frontend/patches/livekit-client.esm.mjs` | Gepatchtes SDK-Bundle (id-0 + 60s Timeouts) |
| `frontend/patches/patch-livekit-client.py` | Reproduzierbares Patch-Skript |
| `frontend/patches/check-livekit-patch.mjs` | Pre-Build-Guard |

### Infrastructure (k3s Staging)

| Datei | Änderung |
|-------|----------|
| `infrastructure/kubernetes/staging/livekit-server-deployment.yaml` | Server Deployment + Service (⚠️ Service-Selector auf Helm-Labels korrigiert, 9.6) |
| `infrastructure/kubernetes/staging/livekit-configmap.yaml` | Server-Konfiguration |
| `infrastructure/kubernetes/staging/livekit-server-values.yaml` | Helm Values (CPU-Limit 1000m, 9.7) |
| `infrastructure/kubernetes/staging/livekit-egress-deployment.yaml` | Egress Deployment (Referenz) |
| `infrastructure/kubernetes/staging/livekit-egress-configmap.yaml` | Egress-Konfiguration |
| `infrastructure/kubernetes/staging/egress-values.yaml` | Helm Values + hostNetwork-Doku |
| `infrastructure/kubernetes/staging/livekit-secrets.yaml` | API-Keys |
| `infrastructure/kubernetes/staging/network-policies.yaml` | NetworkPolicies (Helm-Labels) |

### Dokumentation (docs/)

| Datei | Inhalt |
|-------|--------|
| `LIVEKIT_INTEGRATION_PLAN.md` | Gesamtplan + NetworkPolicy-Fix + hostNetwork-Fix |
| `LIVEKIT_RECORDING_PIPELINE.md` | Pipeline-Beschreibung + Testergebnisse |
| `LIVEKIT_13S_DISCONNECT_ROOT_CAUSE_2026-08-07.md` | 13s-Disconnect Root Cause |
| `LIVEKIT_15S_DISCONNECT_ROOT_CAUSE_2026-08-07.md` | 15s-Disconnect Root Cause |
| `LIVEKIT_15S_WEBSOCKET_TIMEOUT_ROOT_CAUSE_2026-08-08.md` | WebSocket-Timeout Analysis |
| `LIVEKIT_CPU_FIX_2026-08-08.md` | CPU-Underprovisionierung |
| `LIVEKIT_FORCE_RELAY_CACHE_2026-08-08.md` | ICE-Config-Cache Reset |
| `LIVEKIT_ICE_TRANSPORT_POLICY_RELAY_2026-08-08.md` | ICE-Transport-Policy |
| `LIVEKIT_RELAY_RECONNECT_LOOP_2026-08-07.md` | Reconnect-Loop Analysis |
| `LIVEKIT_TURN_CLIENT_FIX_2026-08-07.md` | TURN-Client Fix |
| `LIVEKIT_TURN_UDP_FIX_2026-08-07.md` | TURN-UDP Fix |
| `LIVEKIT_TURN_TCP_FALLBACK_PLAN_2026-08-07.md` | TURN-TCP-Fallback Plan |
| `LIVEKIT_TURN_TLS_CONFIGURATION_2026-08-07.md` | TURN-TLS Konfiguration |
| `MEETINGROOM_CODE_ANALYSIS_2026-08-07.md` | MeetingRoom Code-Analyse |
| `MEETINGROOM_LIVEKIT_ANALYSIS_2026-08-07.md` | MeetingRoom LiveKit-Analyse |
| `NETWORK_ANALYSIS_2026-08-07.md` | Netzwerk-Analyse |
| `RECORDING_START_GUARD_FIX_2026-08-06.md` | Recording Start Guard |
| `PIPELINE_TEST_PLAN.md` | Pipeline-Test-Plan |
| `PIPELINE_TEST_RESULTS.md` | Pipeline-Test-Ergebnisse |

---

## 12. Lessons Learned

### 12.1 hostNetwork in k3s

** Regel:** Wenn ein Service `hostNetwork: true` nutzt, müssen ALLE Clients, die ihn erreichen müssen, entweder ebenfalls `hostNetwork: true` haben ODER der Service muss über eine ClusterIP erreichbar sein (was in k3s mit Calico nicht zuverlässig funktioniert).

**Empfehlung:** LiveKit Server UND Egress sollten immer beide `hostNetwork: true` haben.

### 12.2 Helm-Chart vs. eigene YAML

** Regel:** Wenn das Helm-Chart ein Feld nicht in Values unterstützt (z.B. `hostNetwork`), muss der `kubectl patch` nach jedem `helm upgrade` erneut angewendet werden. Dokumentieren in `egress-values.yaml`.

### 12.3 NetworkPolicy mit hostNetwork-Pods

** Regel:** Calico NetworkPolicies werden an der veth-Schnittstelle angewendet. HostNetwork-Pods haben keine veth → Policies werden NICHT angewendet. Traffic zu/from hostNetwork-Pods muss über andere Mechanismen kontrolliert werden.

### 12.4 LiveKit SDK-Patches

** Regel:** Wenn der Server eine andere Version als der Client ist, müssen SDK-Patches reproduzierbar sein (Skript + Pre-Build-Guard + Version-Match).

### 12.5 Audio-Only Egress

** Regel:** Nie `layout` oder `preset` bei Audio-Only-Recording setzen. Die offizielle Doku (docs.livekit.io) sagt explizit: diese Parameter erzwingen die Video-Pipeline.

### 12.6 Multi-Tenancy bei Recordings

** Regel:** Egress-Output-Pfade müssen `client_id` enthalten (`{client_id}/recordings/{meeting_id}/...`). Webhook-Deduplication via Redis SETNX (24h TTL) verhindert doppelte Verarbeitung.

### 12.7 Service-Selector: kubectl apply vs. Helm

** Regel:** Nach einem Umstieg von direkter YAML auf Helm dürfen Services NIEMALS per `kubectl apply` mit alten Labels überschrieben werden. Das Helm-Chart rendert den Selector korrekt (`app.kubernetes.io/name` + `app.kubernetes.io/instance`). Ein `app:`-Label im Service-Selector, das kein Pod trägt, erzeugt **0 Endpoints** → alle Service-DNS-Verbindungen (Backend, Egress, Ingress) schlagen mit `Connection refused` fehl.

** Merke:** `kubectl patch --type=merge` ergänzt Selector-Maps nur — für eine Korrektur `--type=json` mit `op: replace` auf `/spec/selector` verwenden.

### 12.8 Ressourcen-Limits: Nutzung messen statt raten

** Regel:** Limits an der realen Nutzung orientieren (`kubectl top pods`). Staging: 1 Teilnehmer audio-only → ~1m CPU reicht; 2000m war überdimensioniert. Änderungen per `kubectl patch` anwenden, wenn Helm die Werte nicht aus Values rendert, und die Werte parallel in den Values-YAMLs dokumentieren.

---

## Anhang: Umgebungsvariablen

```bash
# Backend (.env)
LIVEKIT_URL=ws://livekit-server-staging:7880
LIVEKIT_API_KEY=meeting-api-key
LIVEKIT_API_SECRET=meeting-api-secret-2026-minimum-32-chars!

# Kubernetes Secrets
LIVEKIT_API_KEY=meeting-api-key
LIVEKIT_API_SECRET=meeting-api-secret-2026-minimum-32-chars!

# Egress ConfigMap
S3_ENDPOINT=http://minio-staging:9000
S3_BUCKET=meeting-recordings-staging
S3_ACCESS_KEY=minio_user
S3_SECRET_KEY=minio_password
```

---

*Dieses Dokument fasst die gesamte LiveKit-Migration vom 06.–08.08.2026 zusammen, einschließlich aller Konfigurationen, Fixes und Verifikationsergebnisse.*
