# LiveKit + OnlyOffice — K3s 2-Node Cluster Lösungen

> Stand: 2026-07-03 | k3s Staging 2-Node Cluster | Phase 135-137 abgeschlossen

## 1. LiveKit Recording Pipeline (Phase 135)

### Problem
LiveKit Recording funktionierte nicht — Browser zeigte "pc connection" Error, Egress schlug mit "could not connect after timeout" fehl.

### Root Cause (100% bewiesen via Git-Diff 28.06 vs aktuell)
3 Änderungen seit Commit `9d0b24ba` (28.06) haben die Pipeline kaputt gemacht:
1. `hostNetwork: true` von LiveKit entfernt → ICE Candidates nutzen Pod-IP statt Host-IP
2. `hostPort: 50000/60000` entfernt → UDP Media-Ports nicht auf Host-IP
3. `port_range_start/end: 50000-60000` entfernt → Kein UDP-Bereich für ICE

### Lösung
28.06 Config wiederhergestellt + 2-Node Struktur beibehalten:
- **LiveKit**: `hostNetwork: true` + `hostPort 7880/50000/60000` + `port_range 50000-60000` + `force_tcp: false`
- **Egress**: `hostNetwork: true` + DNS (`ws://livekit-config-staging:7880`) + `nodeSelector` Node 2
- **Secrets**: Alle 4 Komponenten aligniert auf `meeting-api-secret-2026-minimum-32-chars!`

### Dateien
| Datei | Änderung |
|-------|----------|
| `infrastructure/kubernetes/staging/livekit-server-deployment.yaml` | `hostNetwork: true`, `hostPort 7880/50000/60000`, `strategy: Recreate` |
| `infrastructure/kubernetes/staging/livekit-configmap.yaml` | `port_range_start: 50000`, `port_range_end: 60000`, `force_tcp: false` |
| `infrastructure/kubernetes/staging/livekit-egress-deployment.yaml` | `hostNetwork: true`, DNS-Ansatz beibehalten |
| `backend-secrets-staging` | Secret aligniert |

### Was funktioniert
- Recording Start → Egress verbindet sich via WebRTC ✅
- Audio wird aufgezeichnet → MinIO S3 Upload ✅
- Transcription + PV werden generiert ✅
- Recording Status: "completed" ✅
- Start → Pause → Stop → Processing → Completed Flow ✅

### Erkenntnisse
- **hostNetwork ist PFLICHT für WebRTC**: LiveKit Docs: "LiveKit does not support deployment to private clusters."
- **DNS-Ansatz (`ws://livekit-config-staging:7880`) funktioniert**: Muss NICHT auf `localhost` zurückgesetzt werden
- **Git-History PRÜFEN vor Debugging**: Die funktionierende Config war im Commit `9d0b24ba` (28.06)

---

## 2. OnlyOffice Callback Fix (Phase 137)

### Problem
OnlyOffice Editor konnte PDF/DOCX nicht laden. Callback und Download-URLs schlugen mit `ECONNREFUSED 158.180.18.110:443` fehl.

### Root Cause
OnlyOffice (im K8s Cluster) konnte die externe Domain `staging.meeting-automation.com:443` nicht erreichen:
- Callback-URL nutzte Host-Header: `https://staging.meeting-automation.com/api/v1/pv/...`
- Download-URL nutzte Host-Header: `https://staging.meeting-automation.com/api/v1/pv/...`
- OnlyOffice Pod (im Cluster) kann keinen externen Ingress über öffentliche IP erreichen

### Lösung
Callback + Download URLs auf internen K8s Service-DNS umgestellt:
- `http://backend.meeting-automation-staging.svc.cluster.local:8000/api/v1/pv/...`

**Netzwerk-Voraussetzungen** (Phase 137):
- `onlyoffice-policy` NP: DNS (53/UDP+TCP) + Backend (8000/TCP) Egress
- `backend-policy` NP: OnlyOffice als Ingress-Quelle
- `ALLOW_PRIVATE_IP_ADDRESS=true` im OnlyOffice Deployment (bereits konfiguriert)

### Dateien
| Datei | Änderung |
|-------|----------|
| `backend/app/api/v1/pv.py:404-405` | `download_url` + `callback_url` nutzen `settings.ONLYOFFICE_BACKEND_URL` |
| `backend/app/core/config.py:94` | `ONLYOFFICE_BACKEND_URL` Setting (bereits vorhanden) |
| `infrastructure/kubernetes/staging/backend-config.yaml` | `ONLYOFFICE_BACKEND_URL` hinzugefügt |
| `infrastructure/kubernetes/staging/network-policies.yaml` | DNS + Backend Egress in `onlyoffice-policy`, OnlyOffice Ingress in `backend-policy` |

### Offizielle Docs-Basis
- OnlyOffice Docker-README: Kein K8s Deployment Guide
- `ALLOW_PRIVATE_IP_ADDRESS=true`: Offizielles Env-Var für private IPs (K8s ClusterIPs)
- Callback URL: Vom Integrator im Config-Objekt gesetzt → OnlyOffice Server muss sie erreichen können
- Einzigster Supported-Weg: K8s Service-DNS mit `ALLOW_PRIVATE_IP_ADDRESS=true`

### Was funktioniert
- OnlyOffice öffnet PV → Document lädt (kein ECONNREFUSED) ✅
- User editiert → Speichert → Callback `{"error": 0}` ✅
- OnlyOffice Logs: Keine Fehler seit Deploy ✅

### Erkenntnisse
- **K3s Pods können externen HTTPS-Ingress nicht erreichen**: Pods im Cluster können keinen Ingress über die öffentliche IP erreichen (ECONNREFUSED). Traffic muss über K8s Service-DNS geroutet werden.
- **Image Import muss via `sudo k3s ctr image import` erfolgen**: `docker build` + `kubectl rollout restart` reicht NICHT — das Image muss explizit importiert werden.
- **Backend-Pod-Code verifizieren**: Nach Deploy MÜSSN mit `inspect.getsource()` der Code im Pod geprüft werden, nicht nur Settings.

---

## 3. K3s Deploy-Checkliste

### Image Import (KRITISCH)
```bash
# 1. Docker Build
docker build --no-cache -t meeting-automation-backend:staging -f backend/Dockerfile backend/

# 2. Image in k3s importieren (MIT sudo!)
docker save meeting-automation-backend:staging | sudo /usr/local/bin/k3s ctr image import -

# 3. Deployment Image setzen
kubectl set image deployment/backend backend=meeting-automation-backend:staging -n meeting-automation-staging

# 4. Code im Pod verifizieren (NICHT nur Settings!)
kubectl exec $POD -- python3 -c "
import inspect, app.api.v1.pv as pv_mod
print(inspect.getsource(pv_mod.get_onlyoffice_config))
"
```

### NetworkPolicy Änderungen
```bash
# 1. YAML anwenden
kubectl apply -f infrastructure/kubernetes/staging/network-policies.yaml

# 2. Debug-Pod testen
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: debug-<service>
  namespace: meeting-automation-staging
  labels:
    app: <service-label>
spec:
  containers:
  - name: debug
    image: busybox:latest
    command: ["sleep", "300"]
EOF

# 3. DNS testen
kubectl exec debug-<service> -- nslookup backend.meeting-automation-staging.svc.cluster.local

# 4. HTTP testen
kubectl exec debug-<service> -- wget -qO- http://backend.meeting-automation-staging.svc.cluster.local:8000/health

# 5. Cleanup
kubectl delete pod debug-<service>
```

---

## 4. Architektur: K3s 2-Node Cluster

### Node-Verteilung
| Node | Pods |
|------|------|
| Node 1 (`10.0.0.11`) | meeting-db-1 (CNPG) |
| Node 2 (`10.0.0.191`) | backend×2, celery-worker×4, celery-beat, frontend, livekit-server, livekit-egress, redis, minio, n8n, onlyoffice, postgres, rabbitmq, nginx-ingress |

### Network Policies (16)
- `default-deny-all`: Ingress Block für alle Pods
- `onlyoffice-policy`: DNS + Backend Egress (Phase 137)
- `backend-policy`: Frontend + LiveKit + OnlyOffice Ingress
- `livekit-policy`: Egress Redis + Backend + DNS + Ingress von Egress/Backend/0.0.0.0/0
- `livekit-egress-policy`: Egress Redis + MinIO + LiveKit + DNS

### Secrets Alignment
| Komponente | Secret-Wert |
|------------|------------|
| LiveKit ConfigMap `keys` | `meeting-api-secret-2026-minimum-32-chars!` |
| Egress Env `LIVEKIT_API_SECRET` | `meeting-api-secret-2026-minimum-32-chars!` |
| Backend Secret `LIVEKIT_API_SECRET` | `meeting-api-secret-2026-minimum-32-chars!` |
| Backend Config `ONLYOFFICE_BACKEND_URL` | `http://backend.meeting-automation-staging.svc.cluster.local:8000` |
