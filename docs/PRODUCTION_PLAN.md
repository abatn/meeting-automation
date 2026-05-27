# Production Plan — Meeting Automation (Kubernetes)

> Erstellt: 2026-05-27 | Basis: Kubernetes MCP Live-Check + Docker-Compose Vergleich
> **Alle Lösungen: Open Source / Kostenlos**

---

## Aktuelle Lücken (Kubernetes MCP bestätigt)

### Phase 1 — Critical (Sofort notwendig)

| # | Issue | Betroffen | Docker-Vergleich |
|---|---|---|---|
| 1 | **Resource Limits fehlen** | 9/11 Workloads | docker-compose.yml: alle Services haben limits |
| 2 | **Health Probes fehlen** | 7/11 Workloads | docker-compose.yml: alle haben healthcheck |
| 3 | **Kein TLS** (self-signed) | Traefik Ingress | docker-compose.prod.yml: kein TLS |

### Phase 2 — High (Nächste Schritte)

| # | Issue | Betroffen | Open Source Lösung |
|---|---|---|---|
| 4 | **Storage hostpath** | Alle PVCs | **Longhorn** (CNCF) oder **Rook/Ceph** (CNCF) |
| 5 | **Image Registry** | backend/frontend | **Docker Hub** oder **Harbor** (CNCF) |
| 6 | **Keine Backups** | postgres PVC | **Velero + MinIO** (beide CNCF/open source) |
| 7 | **Kein Monitoring** | Cluster | **kube-prometheus-stack** (Prometheus+Grafana, CNCF) |

### Phase 3 — Medium (Optimierung)

| # | Issue | Betroffen | Open Source Lösung |
|---|---|---|---|
| 8 | **Kein HPA** | backend, frontend | Kubernetes HPA (built-in) |
| 9 | **Kein PodAntiAffinity** | Alle Workloads | Kubernetes PodAntiAffinity (built-in) |
| 10 | **Keine PodDisruptionBudget** | backend, frontend | Kubernetes PDB (built-in) |
| 11 | **Nur ein Environment** | main | Kubernetes Namespaces (built-in) |
| 12 | **Kein GitOps** | Manuelle kubectl apply | **ArgoCD** (CNCF) |

---

## Phase 1: Resource Limits + Probes

### Resource Limits (Docker-Konfiguration als Referenz)

```yaml
resources:
  limits:
    memory: <value>
    cpu: <value>
  requests:
    memory: <value>
    cpu: <value>
```

| Workload | Memory Limit | CPU Limit | Memory Request | CPU Request |
|---|---|---|---|---|
| postgres | 512Mi | 0.5 | 256Mi | 100m |
| redis | 512Mi | 0.5 | 128Mi | 50m |
| rabbitmq | 512Mi | 0.5 | 256Mi | 100m |
| minio | 512Mi | 0.5 | 256Mi | 100m |
| n8n | 1Gi | 0.5 | 512Mi | 200m |
| onlyoffice | 2Gi | 1.0 | 1Gi | 500m |
| celery-beat | 512Mi | 0.5 | 256Mi | 100m |
| celery-worker | 1Gi | 1.0 | 512Mi | 200m |
| frontend | 512Mi | 0.5 | 128Mi | 50m |
| traefik | 256Mi | 0.5 | 128Mi | 100m |
| backend | 1Gi | 0.5 | 256Mi | 100m |

### Health Probes (zu ergänzen)

| Workload | Probe Type | Command/Path | Delay | Period | Timeout |
|---|---|---|---|---|---|
| celery-beat | liveness | `celery -A app.tasks.celery_app inspect ping` | 30s | 30s | 5s |
| celery-worker | liveness | `celery -A app.tasks.celery_app inspect ping` | 30s | 30s | 5s |
| frontend | liveness | httpGet `/` port 80 | 15s | 15s | 5s |
| n8n | liveness | httpGet `/healthz` port 5678 | 30s | 30s | 5s |
| redis | liveness | `redis-cli ping` | 15s | 15s | 3s |
| traefik | liveness | httpGet `/ping` port 8080 | 10s | 10s | 3s |
| minio | liveness | httpGet `/minio/health/live` port 9000 | 15s | 15s | 5s |
| rabbitmq | liveness | `rabbitmq-diagnostics check_running` | 30s | 30s | 15s |

---

## Phase 2: Infrastruktur-Härtung (Open Source)

### TLS mit cert-manager (CNCF, kostenlos)

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@meeting.tn
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: traefik
```

### Storage: Longhorn (CNCF, open source) statt EBS

```bash
# Longhorn — Open Source Block Storage für Kubernetes
# Bietet: Replikation, Snapshots, Backups, iSCSI/NFS
helm repo add longhorn https://charts.longhorn.io
helm upgrade --install longhorn longhorn/longhorn \
  --namespace longhorn-system --create-namespace

# Als Default StorageClass setzen
kubectl annotate storageclass longhorn storageclass.kubernetes.io/is-default-class=true
```

Alternativ: **Rook/Ceph** (CNCF) für fortgeschrittene Storage-Anforderungen.

### Image Registry: Docker Hub (kostenlos) oder Harbor (CNCF)

```bash
# Option 1: Docker Hub (kostenlos, 1 privates Image)
docker tag meeting-automation-backend:latest youruser/meeting-automation-backend:latest
docker push youruser/meeting-automation-backend:latest

# Option 2: Harbor (CNCF, self-hosted)
helm repo add harbor https://helm.goharbor.io
helm upgrade --install harbor harbor/harbor \
  --namespace harbor --create-namespace \
  --set expose.type=nodePort \
  --set persistence.enabled=true

# Option 3: Docker Registry (minimal, self-hosted)
kubectl create deployment registry --image=registry:2
kubectl expose deployment registry --port=5000
```

### Backups: Velero + MinIO (beide CNCF/open source)

MinIO läuft bereits im Cluster — nutze es als S3-kompatibles Backup-Ziel!

```bash
# Velero installieren mit MinIO als Storage-Backend
velero install \
  --provider aws \
  --bucket velero-backups \
  --secret-file ./credentials-velero \
  --backup-location-config \
    region=minio,s3ForcePathStyle="true",s3Url=http://minio:9000 \
  --plugins velero/velero-plugin-for-aws:v1.0.0

# credentials-velero Inhalt:
# [default]
# aws_access_key_id = minio_user
# aws_secret_access_key = minio_password_prod

# Tägliches Backup
velero schedule create daily-backup \
  --schedule="0 2 * * *" \
  --include-namespaces meeting-automation \
  --ttl 720h

# Postgres DB-Dump (alternativ, einfacher)
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: meeting-automation
spec:
  schedule: "0 3 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: pg-dump
            image: postgres:15-alpine
            command:
            - sh
            - -c
            - PGPASSWORD=\$POSTGRES_PASSWORD pg_dump -h postgres -U meeting_user meeting_db | gzip > /backup/meeting_db-\$(date +%Y%m%d).sql.gz
            envFrom:
            - secretRef:
                name: postgres-secrets
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
          restartPolicy: OnFailure
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: postgres-backup-pvc
EOF
```

### Monitoring: kube-prometheus-stack (CNCF, open source)

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace

# Dashboard zugänglich machen
kubectl patch svc kube-prometheus-stack-grafana -n monitoring \
  -p '{"spec":{"type":"NodePort"}}'
```

Alternativ: **VictoriaMetrics** (open source, performanter als Prometheus).

---

## Phase 3: Betriebsoptimierung

### HPA für backend (Kubernetes built-in)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
  namespace: meeting-automation
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### PodAntiAffinity (Kubernetes built-in)

```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - backend
        topologyKey: kubernetes.io/hostname
```

### PodDisruptionBudget (Kubernetes built-in)

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: backend-pdb
  namespace: meeting-automation
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: backend
```

### GitOps: ArgoCD (CNCF, open source)

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Zugriff
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

### Repository-Struktur mit ArgoCD + Kustomize

```
├── clusters/
│   ├── dev/        # kind/Minikube
│   └── prod/       # On-Prem / Cloud
├── applications/
│   └── meeting-automation/
│       ├── dev.yaml
│       └── prod.yaml
└── config/
    └── meeting-automation/
        ├── base/
        │   ├── kustomization.yaml
        │   ├── deployment.yaml
        │   └── service.yaml
        ├── overlays/
        │   ├── dev/
        │   └── prod/
```

---

## Architektur (Open Source Stack)

```
┌───────────────────────────────────────────────────────────┐
│                   Kubernetes Cluster                       │
├───────────────────────────────────────────────────────────┤
│  Namespace: meeting-automation                             │
│                                                            │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │ Traefik  │  │ cert-manager │  │ Monitoring          │   │
│  │ Ingress  │  │ (Let's Encrypt)│  │ Prometheus+Grafana │   │
│  └────┬─────┘  └──────────────┘  │ +Loki (CNCF)        │   │
│       │                          └────────────────────┘   │
│  ┌────▼──────────────────────────────────────────────┐    │
│  │          Ingress (TLS via Let's Encrypt)          │    │
│  ├────────┬────────┬────────┬────────┬──────────────┤    │
│  │backend │frontend│ n8n    │onlyoffice│  celery     │    │
│  │ (HPA)  │ (HPA)  │        │         │  w+b        │    │
│  ├────────┴────────┴────────┴────────┴──────────────┤    │
│  │           Services (ClusterIP)                    │    │
│  ├────────┬────────┬────────┬────────┬──────────────┤    │
│  │ postgres│ redis  │rabbitmq│ minio  │  Longhorn    │    │
│  │ (CNPG)  │        │        │(S3+Backup)│(Storage)   │    │
│  └────────┴────────┴────────┴────────┴──────────────┘    │
│                                                            │
│  GitOps: ArgoCD (CNCF)   │   Secrets: SOPS (Mozilla)      │
│  Registry: Harbor (CNCF) │   Backups: Velero+MinIO       │
└───────────────────────────────────────────────────────────┘
```

---

## Umsetzungsreihenfolge

```
Sprint 1 (Sofort):
  └─ Resource Limits + Probes auf alle Workloads

Sprint 2 (1 Woche):
  ├─ cert-manager + Let's Encrypt (kostenlos)
  └─ Image Registry: Docker Hub / Harbor

Sprint 3 (2 Wochen):
  ├─ Longhorn StorageClass (CNCF)
  ├─ CloudNativePG Operator (PostgreSQL HA)
  └─ Velero + MinIO Backups

Sprint 4 (3 Wochen):
  ├─ Prometheus + Grafana + Loki (CNCF)
  └─ HPA + PDB + PodAntiAffinity

Sprint 5 (4 Wochen):
  ├─ ArgoCD GitOps Setup (CNCF)
  ├─ Environment-Separation (Namespaces)
  └─ Sealed Secrets / SOPS für Secrets
```

---

## Lizenz-Übersicht (alle Open Source)

| Komponente | Lizenz | Typ |
|---|---|---|
| **Traefik** | MIT | Ingress Controller |
| **cert-manager** | Apache 2.0 | TLS-Zertifikate |
| **Longhorn** | Apache 2.0 (CNCF) | Block Storage |
| **Rook/Ceph** | Apache 2.0 (CNCF) | Storage (Alternative) |
| **Harbor** | Apache 2.0 (CNCF) | Container Registry |
| **Docker Registry** | Apache 2.0 | Container Registry (minimal) |
| **Velero** | Apache 2.0 (CNCF) | Backup/Restore |
| **MinIO** | AGPL v3 | S3-kompatibler Storage |
| **Prometheus** | Apache 2.0 (CNCF) | Monitoring |
| **Grafana** | AGPL v3 | Dashboards |
| **Loki** | AGPL v3 (CNCF) | Log-Aggregation |
| **ArgoCD** | Apache 2.0 (CNCF) | GitOps |
| **CloudNativePG** | Apache 2.0 (CNCF) | PostgreSQL Operator |
| **Kustomize** | Apache 2.0 | Config Management |
| **SOPS** | MPL 2.0 | Secret Encryption |
| **Sealed Secrets** | Apache 2.0 | Secret Management |

---

## Dateien für Phase 1 (Sofort)

| Datei | Änderung |
|---|---|
| `infrastructure/kubernetes/redis-deployment.yaml` | resources + probes |
| `infrastructure/kubernetes/minio-statefulset.yaml` | resources + probes |
| `infrastructure/kubernetes/rabbitmq-statefulset.yaml` | resources + liveness probe |
| `infrastructure/kubernetes/n8n-deployment.yaml` | resources + probes |
| `infrastructure/kubernetes/onlyoffice-deployment.yaml` | resources |
| `infrastructure/kubernetes/celery-beat-deployment.yaml` | resources + probes |
| `infrastructure/kubernetes/celery-worker-deployment.yaml` | probes |
| `infrastructure/kubernetes/frontend-deployment.yaml` | resources + probes |
| `infrastructure/kubernetes/traefik-deployment.yaml` | resources + probes |
| `infrastructure/kubernetes/postgres-statefulset.yaml` | resources |
