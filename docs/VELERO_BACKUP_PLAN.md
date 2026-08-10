# Velero Backup & Recovery Plan

**Status:** PLAN (kein Deploy durchgeführt)
**Erstellt:** 2026-08-10
**Aktualisiert:** 2026-08-10 (mit Phase-92-Historie)
**Cluster:** Staging (OCI 158.180.18.110) + Production (Contabo 169.58.83.32)

---

## 1. Historischer Kontext (Phase 92)

Velero wurde **bereits am 2026-06-28 (Phase 92)** auf dem Staging-Cluster installiert:

| Eigenschaft | Phase 92 (2026-06-28) | Aktuell (2026-08-10) |
|-------------|----------------------|---------------------|
| Velero installiert | ✅ JA | ❌ NEIN (verloren) |
| Nodes | 2 Nodes (HA) | 1 Node (Rebuild) |
| Bucket `velero-backups` | ✅ Erstellt | ❌ Gelöscht (MinIO-PVC neu) |
| Secret `velero-s3-credentials` | ✅ Konfiguriert | ❌ Gelöscht |
| Schedule `daily-backup` | ✅ Aktiv, Backups COMPLETED | ❌ Keine Schedules |
| Velero BSL | ✅ Available | ❌ Nicht vorhanden |

**Ursache des Verlustes:** Der 2-Node-Cluster wurde mehrfach neu aufgebaut (Phasen 188, 189, 189a-c). Velero, MinIO-Buckets und Secrets gingen bei den Rebuilds verloren. Die MinIO-PVC wurde neu erstellt (aktuell 1.1GiB mit 4 Buckets, kein `velero-backups`).

**Lektion:** Velero muss bei jedem Cluster-Rebuild neu installiert werden. Der Plan muss ein `velero-backups` Recovery-Verfahren für Cluster-Rebuilds enthalten.

---

## 2. Ist-Zustand (aktuell)

### Velero Status

| Eigenschaft | Staging | Production |
|------------|---------|------------|
| Velero installiert | ❌ NEIN | ❌ NEIN |
| Velero CLI | v1.14.0 (auf OCI-Server) | Nicht vorhanden |
| Backup-Backend | Keines | Keines |
| Schedules | Keine | Keine |
| Bestehende Backups | Keine (Phase 92 verloren) | Keine |
| MinIO `velero-backups` Bucket | ❌ Gelöscht | ❌ Nicht vorhanden |

**Fazit:** Velero muss in beiden Clustern frisch installiert werden. Der `velero-backups` Bucket muss neu erstellt werden.

**Update 2026-08-10:** Velero ERFOLGREICH auf Staging installiert (Helm v1.18.1, BSL Available, erstes Backup COMPLETED).

### Cluster-Inventar

#### Staging (OCI 158.180.18.110)

| Eigenschaft | Wert |
|------------|------|
| Node | `instance-20260329-0846` (ARM64, Oracle Linux 9.7) |
| k3s Version | v1.36.2+k3s1 |
| Disk | 183G total, 147G belegt (81%) |
| Namespaces | 10 (meeting-automation-staging, monitoring, cert-manager, cnpg-system, ingress-nginx, longhorn-system, kube-system) |
| StorageClass | `local-path` (Longhorn) |

#### Production (Contabo 169.58.83.32)

| Eigenschaft | Wert |
|------------|------|
| Node | `contabo-prod` (AMD64, Ubuntu 24.04) |
| k3s Version | v1.36.2+k3s1 |
| Disk | 290G total, 237G belegt (82%) |
| Namespaces | 9 (meeting-automation, monitoring, cert-manager, cnpg-system, ingress-nginx, longhorn-system, kube-system) |
| StorageClass | `local-path` (Longhorn) |

### PVC-Inventar (Staging)

| Namespace | PVC | Größe | StorageClass |
|-----------|-----|-------|-------------|
| meeting-automation-staging | `postgres-data-postgres-staging-0` | 10Gi | local-path |
| meeting-automation-staging | `meeting-db-1` | 10Gi | local-path |
| meeting-automation-staging | `minio-data-minio-staging-0` | 10Gi | local-path |
| meeting-automation-staging | `rabbitmq-staging-storage-rabbitmq-staging-0` | 5Gi | local-path |
| meeting-automation-staging | `n8n-staging-pvc` | 1Gi | local-path |
| meeting-automation-staging | `sentinel-models-claim` | 2Gi | local-path |
| meeting-automation-staging | `postgres-backup-pvc` | 5Gi | local-path |
| monitoring | `alertmanager-...-0` | 5Gi | local-path |
| monitoring | `prometheus-...-0` | 5Gi | local-path |
| **Gesamt** | | **53Gi** | |

### PVC-Inventar (Production)

| Namespace | PVC | Größe | StorageClass |
|-----------|-----|-------|-------------|
| meeting-automation | `postgres-data-postgres-0` (via CNPG) | 10Gi | local-path |
| meeting-automation | `meeting-db-1` + `meeting-db-2` | 20Gi | local-path |
| meeting-automation | `minio-data-minio-0` | 10Gi | local-path |
| meeting-automation | `rabbitmq-storage-rabbitmq-0` | 5Gi | local-path |
| meeting-automation | `n8n-pvc` | 1Gi | local-path |
| meeting-automation | `sentinel-models-claim` | 2Gi | local-path |
| meeting-automation | `postgres-backup-pvc` | 5Gi | local-path |
| monitoring | `alertmanager-...-0` | 5Gi | local-path |
| monitoring | `prometheus-...-0` | 10Gi | local-path |
| **Gesamt** | | **68Gi** | |

### Helm Releases (beide Cluster identisch)

| Chart | Version | Namespace |
|-------|---------|-----------|
| cert-manager | v1.15.0 | cert-manager |
| ingress-nginx | 1.15.1 | ingress-nginx |
| kube-prometheus-stack | v0.93.0 | monitoring |
| livekit-server | v1.9.0 | meeting-automation(-staging) |
| livekit-egress | v1.8.4 | meeting-automation(-staging) |
| longhorn | v1.12.0 | longhorn-system |

### Application-Services

| Service | Typ | Namespace | Persistent? |
|---------|-----|-----------|-------------|
| PostgreSQL (CNPG) | StatefulSet | meeting-automation(-staging) | ✅ 10Gi |
| PostgreSQL (legacy) | StatefulSet | meeting-automation(-staging) | ✅ 10Gi |
| MinIO | StatefulSet | meeting-automation(-staging) | ✅ 10Gi |
| RabbitMQ | StatefulSet | meeting-automation(-staging) | ✅ 5Gi |
| n8n | Deployment | meeting-automation(-staging) | ✅ 1Gi |
| Sentinel Models | PVC | meeting-automation(-staging) | ✅ 2Gi |
| Backend | Deployment | meeting-automation(-staging) | ❌ |
| Frontend | Deployment | meeting-automation(-staging) | ❌ |
| Celery Worker | Deployment | meeting-automation(-staging) | ❌ |
| Celery Beat | Deployment | meeting-automation(-staging) | ❌ |
| LiveKit Server | Helm | meeting-automation(-staging) | ❌ |
| LiveKit Egress | Helm | meeting-automation(-staging) | ❌ |
| Redis | Deployment | meeting-automation(-staging) | ❌ |
| OnlyOffice | Deployment | meeting-automation(-staging) | ❌ |
| Prometheus | StatefulSet | monitoring | ✅ 5-10Gi |
| Alertmanager | StatefulSet | monitoring | ✅ 5Gi |

---

## 3. Architektur-Diagramm

```
┌─────────────────────────────────────────────────────────────────┐
│                    Velero Backup Architecture                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐              │
│  │  Staging Cluster  │         │ Production Cluster│              │
│  │  (OCI ARM64)     │         │ (Contabo AMD64)   │              │
│  │                  │         │                    │              │
│  │  ┌────────────┐  │         │  ┌────────────┐   │              │
│  │  │   Velero    │  │         │  │   Velero    │   │              │
│  │  │   Server    │  │         │  │   Server    │   │              │
│  │  └─────┬──────┘  │         │  └─────┬──────┘   │              │
│  │        │         │         │        │           │              │
│  │  ┌─────┴──────┐  │         │  ┌─────┴──────┐   │              │
│  │  │  Backup     │  │         │  │  Backup     │   │              │
│  │  │  StorageLoc │  │         │  │  StorageLoc │   │              │
│  │  └─────┬──────┘  │         │  └─────┬──────┘   │              │
│  └────────┼─────────┘         └────────┼──────────┘              │
│           │                           │                          │
│           │     S3 API (MinIO)         │                          │
│           │                           │                          │
│     ┌─────┴───────────────────────────┴──────┐                   │
│     │         MinIO (S3-compatible)           │                   │
│     │  ┌──────────────┐  ┌──────────────────┐    │                   │
│     │  │ velero-backups│  │ meeting-recordings│    │                   │
│     │  │   (neu)       │  │ meeting-pdfs     │    │                   │
│     │  └──────────────┘  │ sentinel-models  │    │                   │
│     │                    └──────────────────┘    │                   │
│     └────────────────────────────────────────┘                   │
│                                                                  │
│  ┌──────────────────────────────────────────────────┐           │
│  │                  Backup-Targets                    │           │
│  │                                                   │           │
│  │  ✅ PVCs (Postgres, MinIO, RabbitMQ, n8n)        │           │
│  │  ✅ ConfigMaps + Secrets (app-namespace)          │           │
│  │  ✅ Helm Releases (custom resources)              │           │
│  │  ✅ CNPG Cluster CRDs                             │           │
│  │  ✅ NetworkPolicies                               │           │
│  │  ✅ CronJobs                                      │           │
│  │                                                   │           │
│  │  ❌ kube-system (k3s-managed)                     │           │
│  │  ❌ longhorn-system (StorageClass)                │           │
│  │  ❌ cert-manager (re-installierbar)               │           │
│  │  ❌ ingress-nginx (re-installierbar)              │           │
│  │  ❌ Prometheus/Alertmanager (Monitoring-Daten)    │           │
│  │  ❌ ephemeral Pods                                │           │
│  └──────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Backup-Strategie

### RPO (Recovery Point Objective)

| Backup-Typ | Häufigkeit | Aufbewahrung | Begründung |
|------------|-----------|-------------|------------|
| Voll-Backup | Täglich 02:00 | 7 Tage | Kritische Daten (Postgres, MinIO) |
| Inkrementelles Backup | Alle 6 Stunden | 3 Tage | Für schnelle Recovery zwischen Voll-Backups |
| Vor-Deploy-Backup | Manuell (bei jedem Deploy) | 14 Tage | Rollback nach fehlgeschlagenem Deploy |

### RTO (Recovery Time Objective)

| Szenario | Ziel-RTO | Methode |
|----------|---------|---------|
| Kompletter Cluster-Verlust | < 60 Minuten | Velero restore + Helm reinstall |
| Einzelner Namespace | < 15 Minuten | Velero restore (Namespace-spezifisch) |
| Nur PVC-Daten | < 10 Minuten | Velero restore (nur PVs) |
| PostgreSQL Point-in-Time | < 5 Minuten | CNPG Backup (separate Methode) |

### Was MUSS gesichert werden

| Ressource | Priorität | Begründung |
|-----------|----------|------------|
| PostgreSQL PVC (10Gi) | **KRITISCH** | Alle Kundendaten, Sessions, Transkripte |
| MinIO PVC (10Gi) | **KRITISCH** | Meeting-Recordings, PDFs, Storage |
| Sentinel Models PVC (2Gi) | **HOCH** | ML-Modelle für Speaker-Identification |
| RabbitMQ PVC (5Gi) | **MITTEL** | Message-Queue-State (rekonstruierbar, aber aufwendig) |
| n8n PVC (1Gi) | **MITTEL** | Workflow-Execution-State |
| ConfigMaps | **HOCH** | LiveKit-Config, Nginx-Config, App-Config |
| Secrets | **HOCH** | API-Keys, TLS-Certs, DB-Credentials |
| CNPG Cluster CRDs | **HOCH** | PostgreSQL-Operator-State |
| NetworkPolicies | **NIEDRIG** | Rekonstruierbar aus YAML |
| CronJobs | **NIEDRIG** | Rekonstruierbar aus YAML |

### Was KANN weggelassen werden

| Ressource | Begründung |
|-----------|------------|
| kube-system Pods | k3s-managed, werden automatisch neu erstellt |
| longhorn-system | StorageClass-Provider, reinstallierbar |
| cert-manager | Helm-managed, reinstallierbar |
| ingress-nginx | Helm-managed, reinstallierbar |
| Prometheus/Alertmanager | Monitoring-Daten, nicht-kritisch |
| Backend/Frontend Deployments | Stateless, werden aus Docker-Images neu erstellt |
| Celery Worker/Beat | Stateless, werden aus Docker-Images neu erstellt |
| Redis | Cache, wird bei Neustart neu befüllt |

---

## 5. MinIO als Velero-Backend

### Aktuelle MinIO-Bucket-Struktur (verifiziert 2026-08-10)

```
MinIO Buckets (aktuell):
├── meeting-recordings/           # Test-WAV-Dateien (~62KiB, 2 Objekte)
├── meeting-recordings-staging/   # LiveKit OGG-Recordings + JSON (~1MiB)
├── meeting-pdfs/                 # Leer (0B)
├── sentinel-models/              # Qwen GGUF-Modell (1.0GiB)
└── velero-backups/               # NEU — muss erstellt werden (Phase 92 gelöscht)
    ├── staging/                  # Staging-Cluster-Backups
    │   ├── backups/
    │   ├── restores/
    │   └── kubernetes/
    └── production/               # Production-Cluster-Backups
        ├── backups/
        ├── restores/
        └── kubernetes/
```

**Gesamt aktuell:** 1.1GiB, 473 Objekte (hauptsächlich sentinel-models). Kein `velero-backups` Bucket.

### Credential-Secret für Velero

**Historischer Name (Phase 92):** `velero-s3-credentials`
**Neuer Name (konsistent):** `velero-s3-credentials` (gleicher Name wie Phase 92)

```yaml
# velero-credentials-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: velero-s3-credentials
  namespace: velero
type: Opaque
stringData:
  cloud: |
    [default]
    aws_access_key_id=minio_user
    aws_secret_access_key=minio_password
```

### Bucket-Policies

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "AWS": ["*"] },
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::velero-backups/*"
    },
    {
      "Effect": "Allow",
      "Principal": { "AWS": ["*"] },
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::velero-backups"
    }
  ]
}
```

### Lifecycle-Policy

```json
{
  "Rules": [
    {
      "ID": "expire-staging-backups",
      "Status": "Enabled",
      "Expiration": { "Days": 7 },
      "Filter": { "Prefix": "staging/" }
    },
    {
      "ID": "expire-production-backups",
      "Status": "Enabled",
      "Expiration": { "Days": 14 },
      "Filter": { "Prefix": "production/" }
    }
  ]
}
```

---

## 6. Installations-Schritte (Staging)

### Phase 1: MinIO Bucket erstellen

```bash
# Port-Forward zu MinIO
kubectl port-forward -n meeting-automation-staging svc/minio-staging 9400:9000 &

# MinIO Client installieren (falls nicht vorhanden)
curl -sL https://dl.min.io/client/mc/release/linux-arm64/mc -o /usr/local/bin/mc
chmod +x /usr/local/bin/mc

# MinIO Alias konfigurieren
mc alias set staging http://localhost:9400 minio_user minio_password

# Bucket erstellen
mc mb staging/velero-backups
mc mb staging/velero-backups/staging
mc mb staging/velero-backups/production
```

### Phase 2: Velero installieren (Helm)

```bash
# Helm-Repo hinzufügen
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
helm repo update

# Velero installieren
helm install velero vmware-tanzu/velero \
  --namespace velero \
  --create-namespace \
  --set configuration.provider=aws \
  --set configuration.backupStorageLocation.name=default \
  --set configuration.backupStorageLocation.bucket=velero-backups/staging \
  --set configuration.backupStorageLocation.config.region=minio \
  --set configuration.backupStorageLocation.config.s3ForcePathStyle=true \
  --set configuration.backupStorageLocation.config.s3Url=http://minio-staging.meeting-automation-staging.svc:9000 \
  --set credentials.existingSecret=velero-s3-credentials \
  --set snapshotsEnabled=false \  # local-path hat keine CSI-Snapshots
  --set deployNodeAgent=true \
  --set nodeAgent.resources.requests.cpu=200m \
  --set nodeAgent.resources.requests.memory=256Mi \
  --set nodeAgent.resources.limits.cpu=500m \
  --set nodeAgent.resources.limits.memory=512Mi \
  --set initContainers[0].name=velero-plugin-for-aws \
  --set initContainers[0].image=velero/velero-plugin-for-aws:v1.9.0 \
  --set initContainers[0].volumeMounts[0].mountPath=/target \
  --set initContainers[0].volumeMounts[0].name=plugins
```

### Phase 3: Backup-Schedule erstellen

**Historischer Schedule-Name (Phase 92):** `daily-backup`
**Neuer Schedule-Name (konsistent):** `daily-backup`

```bash
# Tägliches Voll-Backup (02:00)
velero schedule create daily-backup \
  --schedule="0 2 * * *" \
  --ttl=168h \
  --include-namespaces=meeting-automation-staging \
  --snapshot-volumes

# Alle 6 Stunden inkrementelles Backup
velero schedule create every-6h \
  --schedule="0 */6 * * *" \
  --ttl=72h \
  --include-namespaces=meeting-automation-staging

# Vor-Deploy-Backup (manuell, konsistent mit Phase 92)
velero backup create pre-deploy-$(date +%Y%m%d-%H%M) \
  --include-namespaces=meeting-automation-staging \
  --snapshot-volumes \
  --ttl=336h
```

### Phase 4: Verifikation

```bash
# Status prüfen
velero get backup-locations
velero get snapshots
velero schedule get
velero backup get

# Erstes Backup manuell auslösen
velero backup create test-backup-001 --include-namespaces=meeting-automation-staging --snapshot-volumes

# Backup-Status prüfen
velero backup describe test-backup-001 --details
velero backup logs test-backup-001
```

---

## 7. Production-Deployment-Plan

### Voraussetzungen

| Voraussetzung | Status | Aktion |
|---------------|--------|--------|
| Velero CLI installiert | ❌ | `curl -sL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc` |
| MinIO erreichbar | ✅ | `minio-0` läuft in `meeting-automation` |
| Velero-Backup-Bucket | ❌ | `mc mb production/velero-backups` |
| Credential-Secret | ❌ | Muss überführt werden |

### Schritt-für-Schritt Plan

#### Schritt 1: MinIO Bucket erstellen (Production)

```bash
ssh root@169.58.83.32

# MinIO Client installieren
curl -sL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc
chmod +x /usr/local/bin/mc

# Port-Forward
kubectl port-forward -n meeting-automation svc/minio 9400:9000 &

# Bucket erstellen
mc alias set prod http://localhost:9400 minio_user minio_password
mc mb prod/velero-backups
mc mb prod/velero-backups/production
```

#### Schritt 2: Velero Credential-Secret

```bash
# Secret erstellen
kubectl create namespace velero

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: velero-s3-credentials
  namespace: velero
type: Opaque
stringData:
  cloud: |
    [default]
    aws_access_key_id=minio_user
    aws_secret_access_key=minio_password
EOF
```

#### Schritt 3: Velero installieren

```bash
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
helm repo update

helm install velero vmware-tanzu/velero \
  --namespace velero \
  --create-namespace \
  --set configuration.provider=aws \
  --set configuration.backupStorageLocation.name=default \
  --set configuration.backupStorageLocation.bucket=velero-backups/production \
  --set configuration.backupStorageLocation.config.region=minio \
  --set configuration.backupStorageLocation.config.s3ForcePathStyle=true \
  --set configuration.backupStorageLocation.config.s3Url=http://minio.meeting-automation.svc:9000 \
  --set credentials.existingSecret=velero-s3-credentials \
  --set snapshotsEnabled=false \  # local-path hat keine CSI-Snapshots
  --set deployNodeAgent=true \
  --set nodeAgent.resources.requests.cpu=200m \
  --set nodeAgent.resources.requests.memory=256Mi \
  --set nodeAgent.resources.limits.cpu=500m \
  --set nodeAgent.resources.limits.memory=512Mi \
  --set initContainers[0].name=velero-plugin-for-aws \
  --set initContainers[0].image=velero/velero-plugin-for-aws:v1.9.0 \
  --set initContainers[0].volumeMounts[0].mountPath=/target \
  --set initContainers[0].volumeMounts[0].name=plugins
```

#### Schritt 4: Backup-Schedules

```bash
# Tägliches Voll-Backup (02:00 Production-Time = 01:00 UTC, Tunisia = UTC+1)
# Historischer Name (Phase 92): daily-backup
velero schedule create daily-backup \
  --schedule="0 1 * * *" \
  --ttl=336h \
  --include-namespaces=meeting-automation \
  --snapshot-volumes

# Vor-Deploy-Backup (manuell, von CI/CD ausgelöst)
# Wird in deploy-production.yml als Step hinzugefügt
```

#### Schritt 5: CI/CD Integration

In `.github/workflows/deploy-production.yml` vor dem Deploy einfügen:

```yaml
- name: Velero Pre-Deploy Backup
  run: |
    export KUBECONFIG=$(pwd)/kubeconfig-prod
    velero backup create pre-deploy-${{ github.sha }} \
      --include-namespaces=meeting-automation \
      --snapshot-volumes \
      --ttl=336h \
      --wait
    echo "✅ Velero backup created: pre-deploy-${{ github.sha }}"
```

#### Schritt 6: Verifikation

```bash
# Status prüfen
velero get backup-locations
velero schedule get

# Erstes Backup auslösen
velero backup create prod-test-backup-001 \
  --include-namespaces=meeting-automation \
  --snapshot-volumes

# Prüfen
velero backup describe prod-test-backup-001 --details
velero backup logs prod-test-backup-001
```

---

## 8. Restore-Verfahren

### Szenario A: Kompletter Cluster-Verlust

```bash
# 1. Neuen k3s-Cluster aufsetzen
# 2. Velero installieren (siehe Phase 2)
# 3. MinIO erreichbar machen
# 4. Restore ausführen

velero restore create --from-backup <BACKUP-NAME> \
  --include-namespaces=meeting-automation \
  --restore-volumes=true \
  --wait

# 5. Helm Releases reinstallieren (falls nicht im Backup)
helm install livekit-server vmware-tanzu/livekit-server ...
helm install livekit-egress vmware-tanzu/livekit-egress ...
```

### Szenario B: Namespace-Datenverlust

```bash
# Nur den betroffenen Namespace restoren
velero restore create --from-backup <BACKUP-NAME> \
  --include-namespaces=meeting-automation \
  --selector-match=app in (backend,frontend) \
  --restore-volumes=true
```

### Szenario C: Nur PVC-Daten

```bash
# Nur Persistent Volumes restoren
velero restore create --from-backup <BACKUP-NAME> \
  --include-resources=persistentvolumeclaims,persistentvolumes \
  --restore-volumes=true
```

### Szenario D: PostgreSQL Point-in-Time Recovery

```bash
# Velero restore ist NICHT für Point-in-Time Recovery gedacht
# Dafür: CNPG Backup/Restore

# CNPG Backup (läuft bereits als CronJob)
kubectl exec -n meeting-automation postgres-backup-XXXXX -- \
  pg_dump -U postgres meeting_db > /backup/meeting_db_$(date +%Y%m%d).sql

# CNPG Restore
kubectl exec -n meeting-automation postgres-staging-0 -- \
  psql -U postgres meeting_db < /backup/meeting_db_20260810.sql
```

---

## 9. Monitoring & Alerting

### Velero-Metriken für Prometheus

Velero exposeiert Metriken auf Port 8085:

```yaml
# ServiceMonitor für Velero
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: velero
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: velero
  namespaceSelector:
    matchNames:
      - velero
  endpoints:
    - port: http-metrics
      interval: 60s
```

### Wichtige Metriken

| Metrik | Beschreibung | Alert-Schwelle |
|--------|-------------|----------------|
| `velero_backup_successful` | Backup erfolgreich | = 0 nach Schedule |
| `velero_backup_duration_seconds` | Backup-Dauer | > 3600s (1h) |
| `velero_backup_partial_failure_count` | Teilweise fehlgeschlagen | > 0 |
| `velero_restore_successful` | Restore erfolgreich | = 0 (nach Restore) |
| `velero_backup_bytes_downloaded` | Backup-Größe | > 50Gi (unnormal) |

### Alerting Rules

```yaml
# PrometheusRule für Velero
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: velero-alerts
  namespace: monitoring
spec:
  groups:
    - name: velero
      rules:
        - alert: VeleroBackupFailed
          expr: velero_backup_successful == 0
          for: 1h
          labels:
            severity: critical
          annotations:
            summary: "Velero backup {{ $labels.schedule }} failed"
            
        - alert: VeleroBackupTooOld
          expr: time() - velero_backup_last_successful_timestamp > 86400
          for: 30m
          labels:
            severity: warning
          annotations:
            summary: "Velero backup is older than 24 hours"
            
        - alert: VeleroBackupDurationHigh
          expr: velero_backup_duration_seconds > 3600
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Velero backup taking longer than 1 hour"
```

### Tägliches Monitoring (Checkliste)

```bash
# Velero Status prüfen
velero backup get | tail -5
velero schedule get
velero backup-location get

# Letztes Backup prüfen
velero backup describe $(velero backup get -o json | jq -r '.items[-1].metadata.name') --details

# Backup-Logs prüfen
velero backup logs $(velero backup get -o json | jq -r '.items[-1].metadata.name') | tail -20
```

---

## 10. Zusammenfassung

### Nächste Schritte

| Priorität | Schritt | Aufwand | Risiko |
|-----------|---------|---------|--------|
| **P0** | MinIO Bucket `velero-backups` erstellen | 5 Min | Niedrig |
| **P0** | Velero Credential-Secret erstellen | 5 Min | Niedrig |
| **P0** | Velero via Helm installieren (Staging) | 15 Min | Mittel |
| **P0** | Erstes Backup ausführen & verifizieren | 10 Min | Niedrig |
| **P1** | Backup-Schedules konfigurieren | 5 Min | Niedrig |
| **P1** | Velero ServiceMonitor + Alerting | 10 Min | Niedrig |
| **P1** | Restore-Test durchführen | 30 Min | Hoch |
| **P2** | Production-Deployment | 60 Min | Hoch |
| **P2** | CI/CD Pre-Deploy-Backup integrieren | 15 Min | Niedrig |
| **P2** | Dokumentation (diese Datei) | ✅ Erledigt | Keins |

### Geschätzter Gesamtaufwand

| Phase | Aufwand |
|-------|---------|
| Staging installieren + testen | ~2 Stunden |
| Production deployen | ~1 Stunde |
| CI/CD integrieren | ~30 Minuten |
| **Gesamt** | **~3.5 Stunden** |

### Risiken

| Risiko | Impact | Gegenmaßnahme |
|--------|--------|---------------|
| Local-Path Storage != S3 | Velero kann PVs nicht snapshotten | CSI-Snapshotter mit Longhorn aktivieren |
| MinIO Speicherplatz reicht nicht | Backups schlagen fehl | MinIO PVC von 10Gi auf 20Gi erhöhen |
| Velero zu groß für 1-Node-Cluster | Ressourcen-Konkurrenz | CPU/Memory-Limits setzen |
| ARM64 vs AMD64 Image-Kompatibilität | Velero-Plugins laufen nicht | Multi-Arch Images verwenden |

---


---

## 13. Installations-Lektionen (2026-08-10)

### Helm-Chart v1.18.1 Breaking Changes

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| `configuration.backupStorageLocation: Invalid type. Expected: array` | BSL muss als Array `[0]` übergeben werden | `--set 'configuration.backupStorageLocation[0].name=default'` |
| `provider is required` (in BSL) | Top-level `configuration.provider` entfernt | Provider in jedem BSL-Item setzen: `--set 'configuration.backupStorageLocation[0].provider=aws'` |
| `VolumeSnapshotLocation.spec.provider: Required value` | `snapshotsEnabled=true` erzeugt VSL ohne Provider | `snapshotsEnabled=false` (local-path hat keine CSI-Snapshots) |

### NetworkPolicy Fix

| Problem | Lösung |
|---------|-------|
| `default-deny-all` in `meeting-automation-staging` blockiert Velero->MinIO | `minio-policy` um Velero-Namespace erweitert: `namespaceSelector: kubernetes.io/metadata.name: velero` |
| BSL `Unavailable` (connection refused) | Erst nach NP-Patch + Velero-Restart wird BSL `Available` |

### MinIO Bucket Struktur

| Fehler | Lösung |
|--------|-------|
| Sub-Buckets `staging/` + `production/` in `velero-backups` | Velero erwartet leeren Bucket-Root — Sub-Buckets löschen |
| `Backup store contains invalid top-level directories` | MinIO `mc rb --force` für Sub-Buckets |

### Korrekter Helm-Befehl (fertig)

```bash
helm install velero vmware-tanzu/velero   --namespace velero   --create-namespace   --set 'configuration.backupStorageLocation[0].name=default'   --set 'configuration.backupStorageLocation[0].provider=aws'   --set 'configuration.backupStorageLocation[0].bucket=velero-backups'   --set 'configuration.backupStorageLocation[0].config.region=minio'   --set 'configuration.backupStorageLocation[0].config.s3ForcePathStyle=true'   --set 'configuration.backupStorageLocation[0].config.s3Url=http://minio-staging.meeting-automation-staging.svc:9000'   --set 'credentials.existingSecret=velero-s3-credentials'   --set 'snapshotsEnabled=false'   --set 'deployNodeAgent=true'   --set 'nodeAgent.resources.requests.cpu=200m'   --set 'nodeAgent.resources.requests.memory=256Mi'   --set 'nodeAgent.resources.limits.cpu=500m'   --set 'nodeAgent.resources.limits.memory=512Mi'   --set 'initContainers[0].name=velero-plugin-for-aws'   --set 'initContainers[0].image=velero/velero-plugin-for-aws:v1.9.0'   --set 'initContainers[0].volumeMounts[0].mountPath=/target'   --set 'initContainers[0].volumeMounts[0].name=plugins'
```

## 11. Offene Fragen

| Frage | Entscheidung nötig | Vorschlag |
|-------|-------------------|-----------|
| Soll Velero in **meeting-automation** Namespace laufen oder eigenes **velero** Namespace? | Ja | Eigenes `velero` Namespace (saubere Trennung) |
| Soll der Pre-Deploy-Backup in CI/CD **blockierend** sein (wenn Backup fehlschlägt, kein Deploy)? | Ja | Ja, blockierend für Production, Warning für Staging |
| Soll CNPG Backup (Point-in-Time) **zusätzlich** zu Velero laufen? | Ja | Ja — Velero für Cluster-State, CNPG für DB-Point-in-Time |
| Soll Velero auch **monitoring** Namespace sichern? | Ja | Nein — Prometheus/Alertmanager-Daten nicht kritisch |
| Soll der Velero-Backup-Bucket **verschlüsselt** werden? | Ja | Server-Side Encryption mit MinIO |

---

## 12. Cluster-Rebuild Recovery (Lektion aus Phase 92)

**Lektion:** Velero ging bei Cluster-Rebuilds (Phasen 188, 189) komplett verloren —Namespace, CRDs, Buckets, Secrets, Schedules. Bei jedem Rebuild muss Velero neu installiert werden.

### Recovery-Checkliste nach Cluster-Rebuild

| # | Schritt | Befehl | Verifizierung |
|---|---------|--------|---------------|
| 1 | MinIO erreichbar? | `kubectl get pods -A | grep minio` | Pod Running |
| 2 | `velero-backups` Bucket existiert? | `mc ls staging/velero-backups/` | Bucket vorhanden |
| 3 | Velero Namespace erstellen | `kubectl create namespace velero` | Namespace Active |
| 4 | Credential-Secret erstellen | `kubectl apply -f velero-s3-credentials.yaml` | Secret vorhanden |
| 5 | Velero via Helm installieren | `helm install velero vmware-tanzu/velero ...` | Pod Running |
| 6 | BackupStorageLocation prüfen | `velero backup-location get` | Available |
| 7 | Schedule prüfen | `velero schedule get` | daily-backup active |
| 8 | Erstes Backup auslösen | `velero backup create recovery-test` | COMPLETED |

### Automatisierung (empfohlen)

Füge den Velero-Install-Step in `deploy-staging.yml` und `deploy-production.yml` ein (skip-if-exists Pattern, wie Phase 189c für Longhorn):

```yaml
- name: Install Velero if not present (skip-if-exists)
  run: |
    export KUBECONFIG=$(pwd)/kubeconfig-staging
    if kubectl get namespace velero &>/dev/null; then
      echo "✅ velero namespace exists — skipping install"
    else
      echo "📦 Installing Velero..."
      kubectl create namespace velero
      kubectl apply -f infrastructure/kubernetes/staging/velero-s3-credentials.yaml -n velero
      helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts 2>/dev/null || true
      helm repo update
      helm install velero vmware-tanzu/velero -n velero --create-namespace \
        --set configuration.provider=aws \
        --set configuration.backupStorageLocation.bucket=velero-backups/staging \
        --set configuration.backupStorageLocation.config.s3ForcePathStyle=true \
        --set configuration.backupStorageLocation.config.s3Url=http://minio-staging.meeting-automation-staging.svc:9000 \
        --set credentials.existingSecret=velero-s3-credentials \
        --wait --timeout 10m || echo "⚠️ Warning: Velero install failed"
    fi
```
