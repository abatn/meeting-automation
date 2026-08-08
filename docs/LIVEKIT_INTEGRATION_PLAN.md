# LiveKit Integration — Minimaler Plan

**Erstellt:** 2026-06-05 | **Ziel:** Echtzeit-Audio für alle Teilnehmer + Recording → Pipeline
**Aktualisiert:** 2026-08-12 | **NetworkPolicy-Fix für Helm-deployed Pods**

---

## Architektur

```
Browser ←──→ LiveKit SFU ←──→ Browser
              │
              └── Egress → S3 → Celery Pipeline (unverändert!)
```

**Was bleibt:** TranscriptionTasks, Gladia, Speaker ID, PV, Actions, TranscriptionViewer, PVValidator
**Was sich ändert:** AudioRecorder + MediaRecorder → LiveKit SDK

---

## Dateien (5 gesamt)

### NEU (3 Dateien)

| Datei | Zeilen | Inhalt |
|-------|--------|--------|
| `docker-compose.yml` (Änderung) | +15 | LiveKit Server Container |
| `backend/app/services/livekit_service.py` | ~80 | Room/Token/Egress API |
| `backend/app/api/v1/livekit.py` | ~40 | Token-Endpoint + Webhook |

### GEÄNDERT (3 Dateien)

| Datei | Zeilen | Inhalt |
|-------|--------|--------|
| `backend/app/services/meeting_service.py` | +3 | `create_meeting()` → LiveKit Room |
| `frontend/src/components/meetings/MeetingRoom.tsx` | ~30 | `<LiveKitRoom>` statt `AudioRecorder` |
| `backend/app/services/recording_service.py` | ~20 | Egress → S3 statt MediaRecorder |

### ENTFERNT (2 Dateien)

| Datei | Grund |
|-------|-------|
| `frontend/src/hooks/useAudioRecorder.ts` | LiveKit übernimmt |
| `frontend/src/components/meetings/AudioRecorder.tsx` | LiveKit ControlBar |

---

## Phase 1: Docker (15 Minuten)

```yaml
# docker-compose.yml — NEU
livekit-server:
  image: livekit/livekit-server:latest
  restart: unless-stopped
  ports:
    - "7880:7880"      # HTTP/WS Signalisierung
    - "7881:7881/udp"  # RTC/UDP Medien
  volumes:
    - ./livekit.yaml:/etc/livekit.yaml
  command: --config /etc/livekit.yaml
```

```yaml
# livekit.yaml — NEU
port: 7880
rtc:
  port_range_start: 7881
  port_range_end: 7881
  use_external_ip: false  # Docker intern
keys:
  meeting-api-key: meeting-api-secret-2026
logging:
  level: info
```

**Kein coturn nötig** (Docker intern = kein NAT)

---

## Phase 2: Backend (1 Tag)

### livekit_service.py (~80 Zeilen)

```python
from livekit.api import LiveKitAPI, AccessToken, VideoGrants

class LiveKitService:
    def __init__(self):
        self.api = LiveKitAPI(
            url=settings.LIVEKIT_URL,
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )

    async def create_room(self, meeting_id: str):
        """Room bei Meeting-Erstellung"""
        await self.api.room.create_room(
            name=meeting_id,
            empty_timeout=300,
            max_participants=50,
        )

    async def generate_token(self, meeting_id: str, user_id: str) -> str:
        """JWT für Frontend"""
        token = AccessToken(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        token.identity = user_id
        token.add_grant(VideoGrants(
            room_join=True,
            room=meeting_id,
            can_publish=True,
            can_subscribe=True,
        ))
        return token.to_jwt()

    async def start_egress(self, meeting_id: str, file_key: str) -> str:
        """Recording → MinIO/S3"""
        from livekit.protocol.egress import EncodedFileOutput
        from livekit.api import S3Upload

        output = EncodedFileOutput(
            filepath=f"{file_key}.ogg",
            s3=S3Upload(
                access_key=settings.S3_ACCESS_KEY,
                secret=settings.S3_SECRET_KEY,
                bucket=settings.S3_BUCKET,
                endpoint=settings.S3_ENDPOINT,
            ),
        )
        info = await self.api.egress.start_room_composite_egress(
            room_name=meeting_id, file=output,
        )
        return info.egress_id
```

### api/v1/livekit.py (~40 Zeilen)

```python
router = APIRouter()

@router.post("/meetings/{meeting_id}/livekit/token")
async def get_livekit_token(meeting_id: str, user=Depends(get_current_user)):
    service = LiveKitService()
    token = await service.generate_token(meeting_id, user.id)
    return {"token": token, "server_url": settings.LIVEKIT_URL}

@router.post("/livekit/webhooks")
async def livekit_webhook(request: Request):
    """Egress completed → Celery Pipeline starten"""
    data = await request.json()
    if data.get("event") == "egress.completed":
        meeting_id = data["room_name"]
        file_key = data["file_location"]
        # Recording erstellen + Pipeline triggern
        process_recording.delay(recording_id, file_key)
    return {"ok": True}
```

### meeting_service.py (+3 Zeilen)

```python
async def create_meeting(self, ...):
    # Bestehende Logik...
    # NEU: LiveKit Room erstellen
    livekit = LiveKitService()
    await livekit.create_room(meeting.id)
```

---

## Phase 3: Frontend (1-2 Tage)

### Dependencies

```bash
npm install @livekit/components-react livekit-client
```

### MeetingRoom.tsx (~30 Zeilen geändert)

```tsx
import { LiveKitRoom, VideoConference, ControlBar } from '@livekit/components-react';
import '@livekit/components-styles';

function MeetingRoom({ meetingId }) {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    api.post(`/meetings/${meetingId}/livekit/token`)
      .then(res => setToken(res.data.token));
  }, [meetingId]);

  if (!token) return <Loading />;

  return (
    <LiveKitRoom token={token} serverUrl="ws://localhost:7880" connect={true}>
      <VideoConference />
      <ControlBar />
    </LiveKitRoom>
  );
}
```

**Das war's.** `<VideoConference />` rendert automatisch:
- Audio für alle Teilnehmer
- Speaker Detection
- Teilnehmerliste
- Mic/Cam Toggle
- Screen Share Button

---

## Recording Pipeline (unverändert!)

```
LiveKit Egress → OGG nach MinIO/S3
                    ↓
        Celery: process_recording.delay()
                    ↓
        Gladia V2 Transkription
                    ↓
        Speaker Identification (ONNX)
                    ↓
        PV Generierung (Mistral)
                    ↓
        Action Assignment
                    ↓
        Frontend: TranscriptionViewer + PVValidator
```

**Keine Änderung** an `transcription_tasks.py`, `gladia_service.py`, `pv_service.py`, `action_service.py`.

---

## Env Variablen (.env)

```
LIVEKIT_URL=ws://livekit-server:7880
LIVEKIT_API_KEY=meeting-api-key
LIVEKIT_API_SECRET=meeting-api-secret-2026
```

---

## Zeitplan

| Phase | Beschreibung | Zeit |
|-------|-------------|------|
| 1 | Docker (livekit-server + yaml) | 15 Min |
| 2 | Backend (service + api + meeting_service) | 1 Tag |
| 3 | Frontend (MeetingRoom + Dependencies) | 1-2 Tag |
| **Total** | | **2-3 Tage** |

---

## NetworkPolicy-Konfiguration (Staging)

**Wichtig:** Alle NetworkPolicies müssen **zwei Label-Sets** unterstützen:
1. **Alte Labels** (`app: livekit-server-staging`) — für manuell erstellte Pods
2. **Helm-Labels** (`app.kubernetes.io/name: livekit-server-staging`) — für Helm-deployed Pods

### Betroffene Policies

| Policy | Pod-Selector | Ingress/Egress |
|--------|-------------|----------------|
| `livekit-policy` | `app: livekit-server-staging` + `app.kubernetes.io/name: livekit-server-staging` | Ingress von Egress + Backend |
| `livekit-egress-policy` | `app: livekit-egress-staging` + `app.kubernetes.io/name: egress` | Egress zu Server |
| `redis-policy` | `app: redis-staging` | Ingress von Egress + Server |
| `backend-policy` | `app: backend` | Ingress von LiveKit Server |

### Bekannter Fehler (2026-08-12)

**Problem:** Helm-deployed Egress-Pod (`app.kubernetes.io/name: egress`) konnte sich nicht mit LiveKit-Server verbinden.

**Ursache:**
- Egress-Pod hat nur Helm-Label: `app.kubernetes.io/name: egress`
- `livekit-policy` erlaubte Ingress nur von `app: livekit-egress-staging`
- `default-deny-all` blockierte den Traffic

**Lösung:**
- Helm-Labels in allen NetworkPolicies ergänzt
- Veraltete duplicate Policies (`livekit-policy-helm`, `livekit-egress-policy-helm`) gelöscht
- Datei: `infrastructure/kubernetes/staging/network-policies.yaml`

### Verifikation

```bash
# Prüfe Ingress-Selector der livekit-policy
kubectl get networkpolicy livekit-policy -n meeting-automation-staging -o jsonpath='{.spec.ingress[0].from}'

# Erwartet: 3 PodSelector (altes Label, Helm-Label, backend)
```

---

## EGRESS_ABORTED: Root Cause & Fix (2026-08-12)

### Symptom
- Egress-Recording bricht nach ~10s mit `EGRESS_ABORTED` ab
- Fehler: `"Start signal not received"`
- Chrome wird gestartet, verbindet sich aber **nicht** mit dem LiveKit-Server

### Root Cause: hostNetwork-Mismatch

Der LiveKit-Server läuft mit `hostNetwork: true` (Pod-IP = Host-IP `10.0.0.191`).
Der Egress-Pod (Helm-Chart) hatte `hostNetwork: false` (Pod-IP `10.42.0.169`).
Traffic von Nicht-hostNetwork-Pod zu hostNetwork-Pod via ClusterIP oder Node-IP
wird in k3s/Calico nicht korrekt geroutet → `Connection refused` (TCP RST).

| Test | Target | Ergebnis | Schlussfolgerung |
|------|--------|----------|------------------|
| Server-Pod (hostNetwork) | 10.0.0.191:7880 | ✅ HTTP 200 | Server lauscht auf :::7880 |
| **Egress-Pod (hostNetwork: false)** | livekit-server-staging:7880 | ❌ Connection refused | **hostNetwork-Mismatch** |
| **Egress-Pod (hostNetwork: false)** | 10.0.0.191:7880 | ❌ Connection refused | **hostNetwork-Mismatch** |
| Egress-Pod (hostNetwork: false) | Redis 10.43.54.118:6379 | ✅ TCP connect | Normale Pods erreichbar |
| **Egress-Pod (hostNetwork: true)** | livekit-server-staging:7880 | ✅ Exit-Code 0 | **Fix bestätigt** |
| **Egress-Pod (hostNetwork: true)** | localhost:7880 | ✅ Exit-Code 0 | **hostNetwork shortcut funktioniert** |
| **Egress-Pod (hostNetwork: true)** | 10.0.0.191:7880 | ✅ Exit-Code 0 | **Direkte Node-IP funktioniert** |

### Fix (2026-08-12, LIVE IM CLUSTER)

```bash
# 1. hostNetwork: true + dnsPolicy patchen
kubectl patch deployment livekit-egress -n meeting-automation-staging --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/hostNetwork","value":true},{"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"}]'

# 2. Rollout restart
kubectl rollout restart deployment/livekit-egress -n meeting-automation-staging
```

**WICHTIG:** Das Helm-Chart rendert `hostNetwork` NICHT aus Values. Nach jedem
`helm upgrade` muss der Patch erneut angewendet werden. Siehe `egress-values.yaml`
für die manuelle Patch-Anleitung.

### Verifikation

```bash
# Connectivity testen (alle 3 müssen Exit-Code 0 liefern)
EGRESS_POD=$(kubectl get pods -n meeting-automation-staging -l app.kubernetes.io/name=egress -o jsonpath='{.items[?(@.status.phase=="Running")].metadata.name}')
kubectl exec -n meeting-automation-staging $EGRESS_POD -- wget -q -O /dev/null --timeout=5 http://livekit-server-staging:7880
kubectl exec -n meeting-automation-staging $EGRESS_POD -- wget -q -O /dev/null --timeout=5 http://localhost:7880
```

### Wichtiger Hinweis: MinIO-Zugang

Der Egress-Pod braucht **keinen direkten MinIO-Zugang**:
- Egress schreibt Recording lokal
- Webhook `egress_ended` löst Celery-Worker aus
- **Celery-Worker** (`transcription_tasks.py`)uploaded via `boto3` nach MinIO
- `minio-policy` erlaubt nur: backend, celery-worker, frontend — das ist korrekt

---

## Production-Deployment (2026-08-08)

### Unterschiede Staging vs Production

| Aspekt | Staging | Production |
|--------|---------|------------|
| Namespace | `meeting-automation-staging` | `meeting-automation` |
| Server-Label | `app.kubernetes.io/name: livekit-server-staging` | `app: livekit-server` |
| Egress-Label | `app.kubernetes.io/name: egress` | `app: livekit-egress` |
| Redis | `redis-staging:6379` | `redis:6379` |
| MinIO | `minio-staging:9000` | `minio:9000` |
| API Keys | `meeting-api-key` | `prod-9a4ac9f9...` |
| TURN | deaktiviert | aktiviert (Port 3478) |
| Deployment-Methode | Helm-Chart | Direkte YAML + Helm Values (Referenz) |

### Production-Dateien

| Datei | Zweck |
|-------|-------|
| `infrastructure/kubernetes/production/livekit-server-deployment.yaml` | Server Deployment + Service |
| `infrastructure/kubernetes/production/livekit-configmap.yaml` | Server-Konfiguration |
| `infrastructure/kubernetes/production/livekit-secrets.yaml` | API-Keys |
| `infrastructure/kubernetes/production/livekit-egress-deployment.yaml` | Egress Deployment |
| `infrastructure/kubernetes/production/livekit-egress-configmap.yaml` | Egress-Konfiguration |
| `infrastructure/kubernetes/production/egress-values.yaml` | Helm Values (Referenz) |
| `infrastructure/kubernetes/production/livekit-server-values.yaml` | Helm Values (Referenz) |
| `infrastructure/kubernetes/production/network-policies.yaml` | NetworkPolicies |

### Production-Deployment-Schritte

```bash
# 1. ConfigMaps + Secrets applyen
kubectl apply -f infrastructure/kubernetes/production/livekit-configmap.yaml -n meeting-automation
kubectl apply -f infrastructure/kubernetes/production/livekit-egress-configmap.yaml -n meeting-automation
kubectl apply -f infrastructure/kubernetes/production/livekit-secrets.yaml -n meeting-automation

# 2. NetworkPolicies applyen
kubectl apply -f infrastructure/kubernetes/production/network-policies.yaml -n meeting-automation

# 3. Deployments applyen
kubectl apply -f infrastructure/kubernetes/production/livekit-server-deployment.yaml -n meeting-automation
kubectl apply -f infrastructure/kubernetes/production/livekit-egress-deployment.yaml -n meeting-automation

# 4. Verifizierung
kubectl get pods -n meeting-automation | grep livekit
kubectl logs -n meeting-automation deployment/livekit-server --since=5m | grep -i 'listening\|started'
```

### WICHTIG: hostNetwork für Production

Falls Production auf Helm-Chart umstellt:
```bash
# hostNetwork-Patch nach jedem helm upgrade:
kubectl patch deployment livekit-egress -n meeting-automation --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/hostNetwork","value":true},{"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"}]'
kubectl rollout restart deployment/livekit-egress -n meeting-automation
```

---

## Rollback

1. `LIVEKIT_URL` aus .env entfernen
2. `MeetingRoom.tsx` auf alte Version
3. `AudioRecorder.tsx` reaktivieren
4. LiveKit Container stoppen

---

## Kosten

- **LiveKit Server:** Apache 2.0 (kostenlos)
- **Ressourcen:** ~100MB RAM
- **Bandbreite:** ~50-100 Kbps pro Audio-Stream
