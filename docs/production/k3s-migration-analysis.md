# Kind → k3s Migration: Analyse & Empfehlung

> Erstellt: 2026-06-23 | Basiert auf Phasen 14-32 Erfahrungswerten

## 1. Ist-Zustand (Kind)

| Eigenschaft | Wert |
|-------------|------|
| K8s-Version | v1.31.0, containerd 1.7.18 |
| Host | OCI VM, 4 CPU, 22GB RAM, ARM64, Oracle Linux 9.7 |
| Cluster | 1 Control-Plane Node (`meeting-staging`) |
| Namespace | `meeting-automation-staging` |
| K8s-Manifeste | 40 in `infrastructure/kubernetes/` + 22 in `staging/` |
| LiveKit | Auf Host (Docker Compose) — NICHT im Cluster |
| MinIO | Auf Host (Docker Compose) — NICHT im Cluster |

## 2. Kind-Probleme (bewiesen durch Phasen 14-32)

| Phase | Problem | Root Cause | Kind-spezifisch? |
|-------|---------|-----------|-----------------|
| 14 | LiveKit UDP nicht erreichbar | Kind forwarded NUR TCP 6443 | ✅ JA |
| 15 | LiveKit Connection Error | UDP-NAT in Kind | ✅ JA |
| 16 | ConfigMap Drift | HostAliases für DNS-Hacks | ✅ JA |
| 17 | ICE UDP fehlgeschlagen | Kind-Bridge-Netzwerk | ✅ JA |
| 18 | Kind-Cluster Neuerstellung | Port-Mappings nötig | ✅ JA |
| 20 | Nginx DNS-Resolution | Kind DNS ≠ echtes DNS | ✅ JA |
| 25 | Webhook Port 8080 | Kind NodePort-Mapping | ✅ JA |
| 26 | Zwei MinIO-Instanzen | Host-MinIO ≠ K8s-MinIO | ✅ JA |
| 27 | Egress S3 Endpoint | Host kann K8s-DNS nicht auflösen | ✅ JA |
| 28 | Celery Worker hostAlias | K8s-Pods erreichen Host nicht per DNS | ✅ JA |
| 32 | Network Policies Labels | Kind-Pod-Labels ≠ Manifeste | Teilweise |

**15 von 32 Phasen** waren Kind-spezifische Workarounds.

## 3. k3s Vorteile

| Feature | Kind (aktuell) | k3s (Ziel) |
|---------|---------------|------------|
| LiveKit UDP | ❌ Host-Docker-Workaround | ✅ `hostNetwork: true` im Cluster |
| MinIO | ❌ 2 Instanzen (Host + K8s) | ✅ 1 Instanz im Cluster |
| S3_ENDPOINT | ❌ `minio-host.local:9000` + hostAlias | ✅ `minio-staging:9000` (DNS) |
| Webhook | ❌ `172.18.0.1:8080` (Docker Gateway) | ✅ `backend-svc:8000` (ClusterIP) |
| DNS | ❌ FQDN-Hacks + kube-dns Resolver | ✅ Echter CoreDNS |
| Image-Registry | ❌ `docker save/load` | ✅ Built-in Registry |
| Storage | ❌ hostPath | ✅ Local-Path Provisioner |
| Ingress | Traefik als Deployment | ✅ Traefik built-in (k3s) |
| HostAliases | ❌ 2 Einträge nötig | ✅ Nicht nötig |
| NodePort | ❌ Kind-Port-Mapping | ✅ Direkt auf Host-IP |
| HA | ❌ 1 Node = kein HA | ✅ CloudNativePG möglich |

## 4. Was sich ändern muss

### 4.1 Cluster-Setup
```bash
# Kind entfernen
kind delete cluster --name meeting-staging

# k3s installieren (ohne built-in Traefik, wir nutzen eigenen)
curl -sfL https://get.k3s.io | sh -s - --disable traefik

# Kubeconfig kopieren
cp /etc/rancher/k3s/k3s.yaml ~/.kube/config-staging
```

### 4.2 LiveKit (in den Cluster)
```yaml
# LiveKit Deployment mit hostNetwork für UDP
apiVersion: apps/v1
kind: Deployment
metadata:
  name: livekit-server
  namespace: meeting-automation-staging
spec:
  template:
    spec:
      hostNetwork: true    # Direkter UDP-Zugang
      containers:
      - name: livekit
        image: livekit/livekit-server:latest
        args: ["--config", "/etc/livekit.yaml"]
```

### 4.3 MinIO (in den Cluster)
```yaml
# EIN MinIO statt Zwei
apiVersion: v1
kind: Service
metadata:
  name: minio
  namespace: meeting-automation-staging
spec:
  clusterIP: None  # Headless für StatefulSet
  ports:
  - port: 9000
```

### 4.4 S3 Architecture (vereinfacht)
```
# VORHER (Kind):
S3_ENDPOINT=http://minio-host.local:9000          # Backend (hostAlias)
LIVEKIT_EGRESS_S3_ENDPOINT=http://localhost:9000   # Egress (Host)

# NACHHER (k3s):
S3_ENDPOINT=http://minio-staging:9000              # Backend (DNS)
LIVEKIT_EGRESS_S3_ENDPOINT=http://minio-staging:9000  # Egress (ClusterIP)
```

### 4.5 Webhook (vereinfacht)
```
# VORHER (Kind):
http://172.18.0.1:8080/api/v1/livekit/webhooks    # Docker Gateway

# NACHHER (k3s):
http://backend-svc.meeting-automation-staging.svc.cluster.local:8000/api/v1/livekit/webhooks
```

### 4.6 Setup-Script (vereinfacht)
```bash
# Was ENTFERNT werden kann:
- docker network inspect kind              # hostAlias-Erkennung
- kubectl patch deployment ... hostAliases  # LiveKit + MinIO
- docker save/load für Images              # Built-in Registry
- Port-Mapping Config                      # Direkte NodePorts
- hostAlias für minio-host.local           # DNS funktioniert
- hostAlias für livekit-host.local         # DNS funktioniert
```

## 5. Risiken & Abwägung

| Risiko | Bewertung | Gegenmaßnahme |
|--------|-----------|---------------|
| Datenverlust | 🟡 | Backup vor Migration (pg_dump + MinIO mc mirror) |
| k3s auf ARM64 | ✅ | Offiziell unterstützt von k3s |
| LiveKit UDP in k3s | ✅ | `hostNetwork: true` funktioniert |
| OCI VM Ressourcen | ✅ | 22GB RAM genug für k3s + alle Services |
| Migration Dauer | 🟡 | ~2-3 Stunden |
| Frontend-Image rebuild | 🔴 | Muss für k3s neu gebaut werden |

## 6. Empfehlung

**JA, k3s ist die richtige Entscheidung für dieses Projekt.**

Die gesamte Kind-Architektur war ein Workaround:
- LiveKit auf Host → wegen UDP
- 2 MinIOs → wegen Host/K8s-Isolation
- hostAliases → wegen DNS-Limitierungen
- Port-Mappings → wegen NAT
- Docker save/load → wegen fehlendem Registry

Mit k3s entfällt die Hälfte der Infrastruktur-Komplexität. Die Pipeline (Recording → Transcription → PV) bleibt identisch — nur die Netzwerktopologie wird einfacher.
