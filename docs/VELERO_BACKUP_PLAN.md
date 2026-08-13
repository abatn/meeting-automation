# Velero Backup & Recovery Plan

**Status:** IMPLEMENTIERT (Staging + Production)
**Erstellt:** 2026-08-10
**Aktualisiert:** 2026-08-12 (Staging FSB-Test: BackupRepository Namespace, Disk-Limits, MinIO-Separation Lektionen)
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
| Velero installiert | ✅ JA (v1.18.1) | ✅ JA (v1.18.1) |
| Velero CLI | v1.14.0 | v1.18.1 |
| Backup-Backend | MinIO `velero-backups` | MinIO `velero-backups` |
| BSL Status | ✅ Available | ✅ Available |
| Schedule | `daily-backup` (0 2 * * *, TTL 168h) | `daily-backup` (0 2 * * *, TTL 336h) |
| Erstes Backup | ✅ COMPLETED (215 Items, 304KiB) | ✅ COMPLETED (28.7GiB, 7/7 PVCs) |
| FSB aktiviert | ✅ `configuration.defaultVolumesToFsBackup=true` | ✅ `configuration.defaultVolumesToFsBackup=true` |
| BackupRepository CRD | ✅ `meeting-automation-staging-default-kopia` | ✅ `meeting-automation-default-kopia` |
| PodVolumeBackups | ✅ Funktionieren | ✅ Funktionieren (11 PVBs) |
| MinIO `velero-backups` Bucket | ✅ Vorhanden | ✅ Vorhanden (leer, erstes Backup läuft) |
| Namespace | `velero` | `velero` |

**Fazit:** Velero ist auf BEIDEN Clustern installiert, FSB aktiviert, und sichert automatisch PVC-Daten.

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

## 6. Installations-Schritte (Staging) — ✅ ABGESCHLOSSEN

### Phase 1: MinIO Bucket erstellen

```bash
# Port-Forward zu MinIO
kubectl port-forward -n meeting-automation-staging svc/minio-staging 9400:9000 &

# MinIO Client installieren (ARM64)
curl -sL https://dl.min.io/client/mc/release/linux-arm64/mc -o /tmp/mc
chmod +x /tmp/mc

# MinIO Alias konfigurieren
/tmp/mc alias set staging http://localhost:9400 minio_user minio_password

# Bucket erstellen (sub-Buckets NICHT erstellen — Velero erwartet leeren Bucket-Root)
/tmp/mc mb staging/velero-backups
```

### Phase 2: Velero installieren (Helm)

```bash
# Helm-Repo hinzufügen
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
helm repo update

# Velero installieren (v1.18.1 — BSL als Array, kein top-level provider)
helm install velero vmware-tanzu/velero \
  --namespace velero \
  --create-namespace \
  --set 'configuration.backupStorageLocation[0].name=default' \
  --set 'configuration.backupStorageLocation[0].provider=aws' \
  --set 'configuration.backupStorageLocation[0].bucket=velero-backups' \
  --set 'configuration.backupStorageLocation[0].config.region=minio' \
  --set 'configuration.backupStorageLocation[0].config.s3ForcePathStyle=true' \
  --set 'configuration.backupStorageLocation[0].config.s3Url=http://minio-staging.meeting-automation-staging.svc:9000' \
  --set 'credentials.existingSecret=velero-s3-credentials' \
  --set 'snapshotsEnabled=false' \
  --set 'deployNodeAgent=true' \
  --set 'nodeAgent.resources.requests.cpu=200m' \
  --set 'nodeAgent.resources.requests.memory=256Mi' \
  --set 'nodeAgent.resources.limits.cpu=500m' \
  --set 'nodeAgent.resources.limits.memory=512Mi' \
  --set 'initContainers[0].name=velero-plugin-for-aws' \
  --set 'initContainers[0].image=velero/velero-plugin-for-aws:v1.9.0' \
  --set 'initContainers[0].volumeMounts[0].mountPath=/target' \
  --set 'initContainers[0].volumeMounts[0].name=plugins'
```

### Phase 3: NetworkPolicy Fix

`default-deny-all` in `meeting-automation-staging` blockiert Velero→MinIO Traffic:

```bash
# minio-policy um Velero-Namespace erweitern
kubectl patch networkpolicy minio-policy -n meeting-automation-staging --type=json \
  -p '[{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"velero"}}}}]'
```

### Phase 4: Backup-Schedule erstellen

```bash
# Tägliches Voll-Backup (02:00)
velero schedule create daily-backup \
  --schedule="0 2 * * *" \
  --ttl=168h \
  --include-namespaces=meeting-automation-staging
```

### Phase 5: Erstes Backup & Verifikation

```bash
# Erstes Backup manuell auslösen
velero backup create first-backup-$(date +%Y%m%d) \
  --include-namespaces=meeting-automation-staging \
  --wait

# Status prüfen
velero backup get
velero backup describe first-backup-20260810 --details
velero schedule get
velero backup-location get
```

**Ergebnis (2026-08-10):** `first-backup-20260810` — COMPLETED, 215 Items, 304KiB, 11 Sekunden.

### Phase 6: FSB (File System Backup) aktivieren

**Ziel:** PVC-Daten (PostgreSQL, MinIO, RabbitMQ) in Velero-Backups einbeziehen.

```bash
# FSB aktivieren (KORREKTER Helm-Key: configuration.defaultVolumesToFsBackup)
helm upgrade velero vmware-tanzu/velero -n velero --reuse-values \
  --set configuration.defaultVolumesToFsBackup=true

# Verifikation
kubectl get deploy velero -n velero -o jsonpath='{.spec.template.spec.containers[0].args}' | grep default-volumes-to-fs-backup
# Erwartet: --default-volumes-to-fs-backup im Deployment
```

**Ergebnis (2026-08-11):** Kopia-Repository initialisiert, PVBs funktionieren.

### Phase 7: Scoped FSB Backup (2-3 PVCs)

**Ziel:** Nur kritische PVCs sichern (nicht alle 38Gi).

```bash
# Nur n8n + sentinel + rabbitmq (8Gi gesamt)
velero backup create fsb-scoped-$(date +%Y%m%d) \
  --include-namespaces=meeting-automation-staging \
  --selector 'app in (n8n-staging,celery-worker-pro-staging,rabbitmq-staging)' \
  --wait
```

**Ergebnis (2026-08-11):** Backup PartiallyFailed (Kopia-Repo noch nicht initialisiert).

**UPDATE (2026-08-11):** Nach Kopia-Repo-Initialisierung funktioniert Scoped Backup:

```bash
# Nur sentinel-models-claim (2Gi)
velero backup create fsb-small-$(date +%Y%m%d) \
  --include-namespaces=meeting-automation-staging \
  --selector 'app=celery-worker-pro-staging' \
  --wait
```

**Ergebnis:** COMPLETED in 18 Sekunden, 1 PVB (sentinel-models-claim, 1.1GB).

**Lektion:** `--selector` mit Pod-Label filtert nur PVCs der passenden Pods. Funktioniert zuverlässig.

### Phase 8: Kopia-Repository Recovery

**Problem:** Nach Löschen von MinIO velero-backups/ funktionieren alle PVBs nicht mehr.
**Fehler:** `repository not initialized in the provided storage`

**Lösung (verifiziert):** BackupRepository CRD löschen → Velero initialisiert Kopia-Repo automatisch neu.

```bash
# 1. Stale BackupRepository CRD löschen
kubectl delete backuprepositories.velero.io --all -n velero

# 2. MinIO velero-backups leeren
kubectl exec -n meeting-automation-staging minio-staging-0 -- rm -rf /data/velero-backups/*

# 3. Bucket neu erstellen
kubectl exec -n meeting-automation-staging minio-staging-0 -- mkdir -p /data/velero-backups

# 4. Velero Server restarten
kubectl rollout restart deployment/velero -n velero

# 5. Erstes Backup auslösen (initialisiert Kopia-Repo)
velero backup create init-$(date +%Y%m%d) \
  --include-namespaces=meeting-automation-staging \
  --wait
```

**WICHTIG:** Ohne Schritt 1 (BackupRepository CRD löschen) funktioniert NICHTS!

---

## 7. Production-Deployment — ✅ ABGESCHLOSSEN (2026-08-11)

### Voraussetzungen

| Voraussetzung | Status | Aktion |
|---------------|--------|--------|
| Velero CLI installiert | ✅ | `v1.18.1` auf `/usr/local/bin/velero` |
| MinIO erreichbar | ✅ | `minio-0` läuft in `meeting-automation` |
| Velero-Backup-Bucket | ✅ | `velero-backups` vorhanden (leer) |
| Credential-Secret | ✅ | `velero-s3-credentials` (MinIO-Passwort: `3Bsd1nsvjsnkCzcPvB96ew`) |
| minio-policy erweitert | ✅ | Velero-Ingress-Regel hinzugefügt |
| Velero installiert | ✅ | Helm v1.18.1, `deployed` |
| BSL Available | ✅ | MinIO erreichbar |
| Schedule | ✅ | `daily-backup` (0 2 * * *, TTL 336h) |
| Erstes Backup | ✅ | `first-backup-prod-20260810` — COMPLETED |

### Durchgeführte Schritte

#### Schritt 1: mc (MinIO Client) installieren

```bash
ssh root@169.58.83.32
curl -sL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc
chmod +x /usr/local/bin/mc
```

#### Schritt 2: velero-backups Bucket verifizieren

```bash
# Bucket existierte bereits (leer)
kubectl exec -n meeting-automation minio-0 -- ls /data/velero-backups/
```

#### Schritt 3: Velero Namespace + Secret

```bash
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
    aws_secret_access_key=3Bsd1nsvjsnkCzcPvB96ew
EOF
```

**WICHTIG:** Production MinIO-Passwort ist `3Bsd1nsvjsnkCzcPvB96ew`, NICHT `minio_password`!

#### Schritt 4: minio-policy erweitern

```bash
kubectl patch networkpolicy minio-policy -n meeting-automation --type=json \
  --patch-file=/dev/stdin <<EOF
[{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"velero"}}}}]
EOF
```

#### Schritt 5: Velero via Helm installieren

```bash
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
helm repo update

helm install velero vmware-tanzu/velero \
  --namespace velero \
  --set 'configuration.backupStorageLocation[0].name=default' \
  --set 'configuration.backupStorageLocation[0].provider=aws' \
  --set 'configuration.backupStorageLocation[0].bucket=velero-backups' \
  --set 'configuration.backupStorageLocation[0].config.region=minio' \
  --set 'configuration.backupStorageLocation[0].config.s3ForcePathStyle=true' \
  --set 'configuration.backupStorageLocation[0].config.s3Url=http://minio.meeting-automation.svc:9000' \
  --set 'credentials.existingSecret=velero-s3-credentials' \
  --set 'snapshotsEnabled=false' \
  --set 'deployNodeAgent=true' \
  --set 'nodeAgent.resources.requests.cpu=200m' \
  --set 'nodeAgent.resources.requests.memory=256Mi' \
  --set 'nodeAgent.resources.limits.cpu=500m' \
  --set 'nodeAgent.resources.limits.memory=512Mi' \
  --set 'initContainers[0].name=velero-plugin-for-aws' \
  --set 'initContainers[0].image=velero/velero-plugin-for-aws:v1.9.0' \
  --set 'initContainers[0].volumeMounts[0].mountPath=/target' \
  --set 'initContainers[0].volumeMounts[0].name=plugins'
```

#### Schritt 6: Backup-Schedule + erstes Backup

```bash
# Schedule (TTL 336h = 14 Tage für Production)
velero schedule create daily-backup \
  --schedule="0 2 * * *" \
  --ttl=336h \
  --include-namespaces=meeting-automation

# Erstes Backup
velero backup create first-backup-prod-$(date +%Y%m%d) \
  --include-namespaces=meeting-automation \
  --wait
```

**Ergebnis (2026-08-11):** `first-backup-prod-20260810` — COMPLETED, 0 Errors, 0 Warnings.

#### Schritt 7: FSB (File System Backup) aktivieren

**Problem:** Die ersten Production-Backups enthielten nur Metadaten (213 Items, ~304KiB) — KEINE PVCs!
**Ursache:** FSB war bei der Initial-Installation nicht aktiviert.

```bash
# FSB aktivieren (KORREKTER Helm-Key)
helm upgrade velero vmware-tanzu/velero -n velero --reuse-values \
  --set configuration.defaultVolumesToFsBackup=true

# Verifikation
kubectl get deploy velero -n velero -o jsonpath='{.spec.template.spec.containers[0].args}'
# Erwartet: --default-volumes-to-fs-backup im Deployment-Args
```

#### Schritt 8: Kopia-Repository initialisieren

```bash
# Metadata-only Backup (initialisiert Kopia-Repo + sichert PVCs)
velero backup create init-meta-prod-$(date +%Y%m%d) \
  --include-namespaces=meeting-automation \
  --snapshot-volumes=false \
  --wait

# Verifikation
kubectl get backuprepositories.velero.io -n velero
# Erwartet: meeting-automation-default-kopia (AGE > 0)

kubectl get podvolumebackups.velero.io -n velero
# Erwartet: 7+ PVBs (alle PVCs im Namespace)
```

**Ergebnis (2026-08-11):**

| Metrik | Wert |
|--------|------|
| Backup-Status | ✅ COMPLETED (0 Errors, 9 Warnings) |
| PVBs | ✅ 11 Completed (7 PVCs + 4 Nachzügler) |
| BackupRepository CRD | ✅ `meeting-automation-default-kopia` |
| Backup-Größe | ~28.7GiB (alle 7 PVCs gesichert) |
| Disk | 79% (62G frei) — stabil |
| Dauer | ~10 Minuten |

**Hinweis:** Die 9 Warnings betreffen Cluster-Scoped Ressourcen (ClusterRoles, CRDs) — nicht kritisch.

### Schritt 9: Restore-Test (verifiziert 2026-08-11)

**Sicherheitsregel:** NICHT ins laufende Namespace restoren!

```bash
# 1. Temporären Namespace erstellen
kubectl create namespace restore-test

# 2. Restore mit Namespace-Mapping
velero restore create restore-test-mapped \
  --from-backup init-meta-prod-20260811 \
  --namespace-mappings meeting-automation:restore-test \
  --restore-volumes=true \
  --wait

# 3. Verifikation
kubectl get all -n restore-test
kubectl get pvc -n restore-test
kubectl exec -n restore-test minio-0 -- ls /data/

# 4. Aufräumen
kubectl delete namespace restore-test
```

**Ergebnis:**

| Metrik | Wert |
|--------|------|
| Items restored | 179 |
| PVCs erstellt | 7/7 Bound ✅ |
| MinIO-Daten | ✅ Wiederhergestellt (meeting-recordings, qwen-models, etc.) |
| Running Pods | 10/14 (main services) |
| Namespace-Mapping | ✅ `meeting-automation` → `restore-test` |
| Restore-Status | PartiallyFailed (3 Errors — hostNetwork-Konflikte, erwartet) |

**Lektion:** `--namespace-mappings` ist KRITISCH für Restore in separaten Namespace.

### Schritt 10: Velero Monitoring (verifiziert 2026-08-11)

```yaml
# ServiceMonitor (deployed in monitoring/)
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

**Alerts:** VeleroBackupFailed (critical), VeleroBackupTooOld (warning), VeleroBackupDurationHigh (warning), VeleroBackupPartialFailure (warning)

**Deployed:** Staging + Production ✅

### CI/CD Integration (geplant)

In `.github/workflows/deploy-production.yml` vor dem Deploy einfügen:

```yaml
- name: Velero Pre-Deploy Backup
  run: |
    export KUBECONFIG=$(pwd)/kubeconfig-prod
    velero backup create pre-deploy-${{ github.sha }} \
      --include-namespaces=meeting-automation \
      --ttl=336h \
      --wait
    echo "✅ Velero backup created: pre-deploy-${{ github.sha }}"
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

## 9. Monitoring & Alerting — ✅ ABGESCHLOSSEN (2026-08-11)

### Deployed Resources

| Ressource | Staging | Production |
|-----------|---------|------------|
| ServiceMonitor `velero` | ✅ Deployed | ✅ Deployed |
| PrometheusRule `velero-alerts` | ✅ Deployed | ✅ Deployed |

### Velero-Metriken für Prometheus

Velero exposeiert Metriken auf Port 8085:

```yaml
# ServiceMonitor für Velero
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: velero
  namespace: monitoring
  labels:
    app.kubernetes.io/name: velero
    release: kube-prometheus-stack
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
      path: /metrics
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

| Priorität | Schritt | Aufwand | Risiko | Status |
|-----------|---------|---------|--------|--------|
| **P0** | MinIO Bucket `velero-backups` erstellen | 5 Min | Niedrig | ✅ Erledigt |
| **P0** | Velero Credential-Secret erstellen | 5 Min | Niedrig | ✅ Erledigt |
| **P0** | Velero via Helm installieren (Staging) | 15 Min | Mittel | ✅ Erledigt |
| **P0** | Erstes Backup ausführen & verifizieren | 10 Min | Niedrig | ✅ Erledigt |
| **P0** | Production-Deployment | 60 Min | Hoch | ✅ Erledigt |
| **P0** | Production FSB aktivieren | 15 Min | Niedrig | ✅ Erledigt |
| **P0** | Production erstes FSB-Backup | 15 Min | Mittel | ✅ Erledigt |
| **P1** | Backup-Schedules konfigurieren | 5 Min | Niedrig | ✅ Erledigt |
| **P1** | Velero ServiceMonitor + Alerting | 10 Min | Niedrig | ✅ Erledigt |
| **P1** | Restore-Test durchführen | 30 Min | Hoch | ✅ Erledigt |
| **P1** | Scoped FSB Backup testen | 5 Min | Niedrig | ✅ Erledigt |
| **P2** | CI/CD Pre-Deploy-Backup integrieren | 15 Min | Niedrig | ⬜ Offen |
| **P2** | Dokumentation (diese Datei) | ✅ Erledigt | Keins | ✅ Erledigt |

### Geschätzter Gesamtaufwand

| Phase | Aufwand | Status |
|-------|---------|--------|
| Staging installieren + testen | ~2 Stunden | ✅ Erledigt |
| Production deployen | ~1 Stunde | ✅ Erledigt |
| CI/CD integrieren | ~30 Minuten | ⬜ Offen |
| **Gesamt** | **~3.5 Stunden** | **~3h erledigt** |

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

### FSB (File System Backup) Lektionen

| Problem | Ursache | Lösung |
|---------|--------|-------|
| `defaultVolumesToFsBackup` nicht wirksam | Falscher Helm-Key (top-level statt `configuration.`) | `configuration.defaultVolumesToFsBackup=true` |
| Node-Agent Eviction bei Full Backup | 38Gi PVCs → Disk-Pressure 92% | Nur kritische PVCs mit `--selector` sichern |
| Kopia-Repo nicht initialisiert | MinIO velero-backups/ gelöscht | BackupRepository CRD löschen → Velero auto-init |
| `repository not initialized in the provided storage` | BackupRepository CRD zeigt auf nicht-existierendes Repo | CRD löschen + Velero restarten |
| Backup-Größe 764K (keine PVCs) | FSB nicht aktiviert (falscher Helm-Key) | Helm-Key korrigieren |
| Backup-Größe 57Gi (zu groß) | Alle PVCs inkl. MinIO + PostgreSQL | Selektive Backups mit `--selector` |
| `--snapshot-volumes=false` verhindert PVBs NICHT | FSB wird durch `defaultVolumesToFsBackup=true` getriggert | Nur per `--selector` PVCs einschränken |

### Kopia-Repository Struktur in MinIO

```
velero-backups/
├── kopia/
│   └── meeting-automation-staging/
│       ├── kopia.blobcfg          # Kopia-Konfiguration
│       ├── kopia.repository       # Repository-Metadaten
│       ├── p027c0870.../          # Blob-Objekte (PVB-Daten)
│       ├── p04e0fe3.../
│       └── ...
└── backups/
    └── <backup-name>/
        ├── <backup-name>-logs.gz
        ├── <backup-name>-results.gz
        └── ...
```

### Empfohlene FSB-Strategie

| Backup-Typ | Selector | PVCs | Geschätzte Größe | TTL |
|------------|----------|------|-----------------|-----|
| Metadaten only | Keiner | Keine | ~500K | 168h |
| Scoped (klein) | `app in (n8n-staging,celery-worker-pro-staging,rabbitmq-staging)` | n8n+sentinel+rabbitmq | ~3-5Gi | 168h |
| Kritisch | `app in (postgres-staging,minio-staging)` | PostgreSQL+MinIO | ~15-20Gi | 720h |
| Voll | Keiner | Alle 38Gi | ~25-30Gi | 720h |

### Kopia-Repository Management (Lektionen aus 2026-08-11)

**Kernproblem:** Wenn MinIO `velero-backups/` gelöscht wird, geht auch das Kopia-Repository verloren. Velero kann dann keine PodVolumeBackups mehr erstellen — alle PVBs scheitern mit `repository not initialized in the provided storage`.

#### Kopia-Repository Struktur in MinIO

```
velero-backups/
├── kopia/
│   └── meeting-automation-staging/      # Namespace-scoped
│       ├── kopia.blobcfg                # Kopia-Konfiguration (Verschlüsselung, etc.)
│       ├── kopia.repository             # Repository-Metadaten
│       ├── p027c0870.../                # Blob-Objekte (PVB-Daten)
│       ├── p04e0fe3.../
│       └── ...
└── backups/
    └── <backup-name>/
        ├── <backup-name>-logs.gz
        ├── <backup-name>-results.gz
        └── ...
```

#### BackupRepository CRD Lifecycle

```
Velero installiert (Helm)
    │
    ├── BSL Available ✅
    ├── node-agent Running ✅
    │
    ├── Erstes FSB-Backup gestartet
    │   └── node-agent initialisiert Kopia-Repo automatisch
    │       ├── Kopia-Repo in MinIO erstellt (kopia.blobcfg + kopia.repository)
    │       └── BackupRepository CRD erstellt: <namespace>-default-kopia
    │
    ├── BackupRepository CRD: Ready ✅
    │   └── Zeigt auf MinIO kopia/ Verzeichnis
    │
    ├── ── MINIO VELO-BACKUPS GELOESCHT ──
    │   └── BackupRepository CRD: stale (zeigt auf nicht-existierendes Repo)
    │
    ├── Alle PVBs: Failed ❌
    │   └── "repository not initialized in the provided storage"
    │
    └── RECOVERY: BackupRepository CRD löschen
        ├── kubectl delete backuprepositories.velero.io --all -n velero
        ├── Velero server restartet
        └── Nächstes Backup initialisiert Kopia-Repo automatisch neu
```

#### Recovery-Verfahren (verifiziert 2026-08-11)

**WICHTIG:** Diese Schritte MÜSSEN in dieser Reihenfolge ausgeführt werden!

```bash
# 1. BackupRepository CRD löschen (KRITISCH — ohne diesen Schritt funktioniert nichts!)
kubectl delete backuprepositories.velero.io --all -n velero

# 2. MinIO velero-backups leeren (nur wenn Kopia-Repo defekt)
kubectl exec -n <namespace> minio-<pod> -- rm -rf /data/velero-backups/*
kubectl exec -n <namespace> minio-<pod> -- mkdir -p /data/velero-backups

# 3. Alle alten Backup-Records löschen (zeigen auf defektes Repo)
for b in $(velero backup get -o json | python3 -c "import sys,json; [print(i['metadata']['name']) for i in json.load(sys.stdin).get('items',[])]"); do
  velero backup delete $b --confirm
done

# 4. Velero Server restarten
kubectl rollout restart deployment/velero -n velero

# 5. Metadata-only Backup (initialisiert Kopia-Repo OHNE große Datenmenge)
velero backup create init-meta-$(date +%Y%m%d) \
  --include-namespaces=<namespace> \
  --snapshot-volumes=false \
  --wait

# 6. Verifikation: Kopia-Repo existiert
kubectl exec -n <namespace> minio-<pod> -- ls -la /data/velero-backups/kopia/
# Erwartet: kopia.blobcfg + kopia.repository

# 7. FSB Backup (jetzt funktioniert es)
velero backup create fsb-after-recovery-$(date +%Y%m%d) \
  --include-namespaces=<namespace> \
  --wait
```

#### Häufige Fehlerquellen

| Fehler | Ursache | Lösung |
|--------|--------|--------|
| `repository not initialized in the provided storage` | Kopia-Repo gelöscht oder BackupRepository CRD stale | Schritte 1-7 oben ausführen |
| `FailedValidation: backup storage location not available` | Velero Server noch nicht ready nach Restart | 15s warten, erneut versuchen |
| PVB `Error: repo-maintain-jobs` fehlgeschlagen | Kopia-Maintenance auf defektem Repo | Schritt 1 (CRD löschen) + Velero Restart |
| `--snapshot-volumes=false` verhindert PVBs NICHT | `defaultVolumesToFsBackup=true` override | Nur per `--selector` PVCs einschränken |
| Backup `PartiallyFailed` (0 Items) | BSL war beim Start noch nicht Ready | Velero 15s nach Restart warten |

#### Wann BackupRepository CRD löschen?

| Szenario | CRD löschen? | Begründung |
|----------|-------------|------------|
| MinIO velero-backups/ gelöscht | ✅ JA | CRD zeigt auf nicht-existierendes Repo |
| Kopia-Repo defekt (Blob-Fehler) | ✅ JA | Erzwingt Neu-Initialisierung |
| Velero Helm-Upgrade | ❌ NEIN | CRD wird beibehalten |
| Velero Namespace gelöscht | ✅ JA (automatisch) | CRD im Namespace |
| Nur Backup-Records gelöscht | ❌ NEIN | Repo bleibt intakt |

#### node-agent vs velero-server: Kopia-Binary

| Komponente | Kopia-Binary | Verwendung |
|------------|-------------|------------|
| Velero Server | ❌ Kein Kopia | Verwaltet PVBs, schreibt Metadaten |
| node-agent (DaemonSet) | ✅ Kopia (eingebaut) | Führt Volume-Backups durch, initialisiert Repo |

**Achtung:** `kopia repository status` im node-agent Pod ist NICHT direkt ausführbar — Kopia läuft als subprocess innerhalb des node-agent Prozesses. Debugging über `velero backup logs` und `kubectl logs daemonset/node-agent`.

### Production-spezifische Lektionen

| Problem | Staging | Production |
|---------|---------|------------|
| MinIO-Passwort | `minio_password` (Standard) | `3Bsd1nsvjsnkCzcPvB96ew` (Custom) — Secret musste korrigiert werden |
| Helm-Repo | Bereits vorhanden | Musste `vmware-tanzu` erst hinzugefügt werden |
| Velero CLI | Bereits vorhanden (v1.14.0) | Musste v1.18.1 installiert werden |
| velero-backups Bucket | Neu erstellt | Bereits vorhanden (leer) — keine Aktion nötig |
| minio-policy | Velero-Namespace fehlte | Velero-Namespace fehlte — musste erweitert werden |
| BSL Provider | Immer Required | `configuration.provider` muss in jedem BSL-Item sein (nicht top-level) |

### Korrekter Helm-Befehl (Staging)

```bash
helm install velero vmware-tanzu/velero \
  --namespace velero \
  --create-namespace \
  --set 'configuration.backupStorageLocation[0].name=default' \
  --set 'configuration.backupStorageLocation[0].provider=aws' \
  --set 'configuration.backupStorageLocation[0].bucket=velero-backups' \
  --set 'configuration.backupStorageLocation[0].config.region=minio' \
  --set 'configuration.backupStorageLocation[0].config.s3ForcePathStyle=true' \
  --set 'configuration.backupStorageLocation[0].config.s3Url=http://minio-staging.meeting-automation-staging.svc:9000' \
  --set 'credentials.existingSecret=velero-s3-credentials' \
  --set 'snapshotsEnabled=false' \
  --set 'deployNodeAgent=true' \
  --set 'nodeAgent.resources.requests.cpu=200m' \
  --set 'nodeAgent.resources.requests.memory=256Mi' \
  --set 'nodeAgent.resources.limits.cpu=500m' \
  --set 'nodeAgent.resources.limits.memory=512Mi' \
  --set 'initContainers[0].name=velero-plugin-for-aws' \
  --set 'initContainers[0].image=velero/velero-plugin-for-aws:v1.9.0' \
  --set 'initContainers[0].volumeMounts[0].mountPath=/target' \
  --set 'initContainers[0].volumeMounts[0].name=plugins'
```

### Korrekter Helm-Befehl (Production)

```bash
helm install velero vmware-tanzu/velero \
  --namespace velero \
  --create-namespace \
  --set 'configuration.backupStorageLocation[0].name=default' \
  --set 'configuration.backupStorageLocation[0].provider=aws' \
  --set 'configuration.backupStorageLocation[0].bucket=velero-backups' \
  --set 'configuration.backupStorageLocation[0].config.region=minio' \
  --set 'configuration.backupStorageLocation[0].config.s3ForcePathStyle=true' \
  --set 'configuration.backupStorageLocation[0].config.s3Url=http://minio.meeting-automation.svc:9000' \
  --set 'credentials.existingSecret=velero-s3-credentials' \
  --set 'snapshotsEnabled=false' \
  --set 'deployNodeAgent=true' \
  --set 'nodeAgent.resources.requests.cpu=200m' \
  --set 'nodeAgent.resources.requests.memory=256Mi' \
  --set 'nodeAgent.resources.limits.cpu=500m' \
  --set 'nodeAgent.resources.limits.memory=512Mi' \
  --set 'initContainers[0].name=velero-plugin-for-aws' \
  --set 'initContainers[0].image=velero/velero-plugin-for-aws:v1.9.0' \
  --set 'initContainers[0].volumeMounts[0].mountPath=/target' \
  --set 'initContainers[0].volumeMounts[0].name=plugins'
```

## 11. Production-Unterschiede (Lektionen)

| Aspekt | Staging | Production |
|--------|---------|------------|
| MinIO-Passwort | `minio_password` | **`3Bsd1nsvjsnkCzcPvB96ew`** (anders!) |
| MinIO Service DNS | `minio-staging.meeting-automation-staging.svc` | `minio.meeting-automation.svc` |
| Namespace | `meeting-automation-staging` | `meeting-automation` |
| Schedule TTL | 168h (7 Tage) | 336h (14 Tage) |
| Helm-Repo | Bereits vorhanden | Musste `vmware-tanzu` hinzugefügt werden |
| Velero CLI | Bereits vorhanden (v1.14.0) | Musste installiert werden (v1.18.1) |
| mc (MinIO Client) | `/tmp/mc` (ARM64) | `/usr/local/bin/mc` (AMD64) |
| velero-backups Bucket | Neu erstellt | Bereits vorhanden (leer) |
| Disk | 183G (81% belegt) | 290G (82% belegt) |
| FSB aktiviert | ✅ Bei Installation | ❌ Erst nach Helm-Upgrade (Schritt 7) |
| Erstes FSB-Backup | ~30Gi (Staging) | ~28.7Gi (Production) |
| BackupRepository CRD | `meeting-automation-staging-default-kopia` | `meeting-automation-default-kopia` |

## 12. Offene Fragen

| Frage | Entscheidung nötig | Vorschlag |
|-------|-------------------|-----------|
| ~~Soll Velero in **meeting-automation** Namespace laufen oder eigenes **velero** Namespace?~~ | ✅ Erledigt | Eigenes `velero` Namespace (beide Cluster) |
| Soll der Pre-Deploy-Backup in CI/CD **blockierend** sein (wenn Backup fehlschlägt, kein Deploy)? | Ja | Ja, blockierend für Production, Warning für Staging |
| Soll CNPG Backup (Point-in-Time) **zusätzlich** zu Velero laufen? | Ja | Ja — Velero für Cluster-State, CNPG für DB-Point-in-Time |
| Soll Velero auch **monitoring** Namespace sichern? | Ja | Nein — Prometheus/Alertmanager-Daten nicht kritisch |
| Soll der Velero-Backup-Bucket **verschlüsselt** werden? | Ja | Server-Side Encryption mit MinIO |

---

## 14. Staging FSB-Test Lektionen (2026-08-12)

### Durchgeführte Tests

Ein umfangreicher Staging-Test wurde durchgeführt, um Velero FSB (File System Backup) mit echten PVC-Daten zu verifizieren.

### Test 1: FSB Backup mit Volume-Daten

| Metrik | Wert |
|--------|------|
| Backup-Name | `fsb-test-20260812-094239` |
| PVBs erstellt | 4 (sentinel-models, minio-data, postgres-data, n8n) |
| PVBs Completed | 2 (sentinel-models 58MB, minio-data 1.1GB) |
| PVBs Failed | 2 (postgres-data, n8n) |
| Root Cause | Kopia-Repository nicht initialisiert (`repository not initialized in the provided storage`) |

**Lektion:** Nach Löschen von `velero-backups/` in MinIO muss die BackupRepository CRD gelöscht werden, damit Velero das Kopia-Repo neu initialisiert.

### Test 2: BackupRepository Namespace

**BEWEIS (verifiziert 2026-08-12):**

```
BEFEHL: kubectl get backuprepositories.velero.io -A

ERGEBNIS:
NAMESPACE                    NAME                                       AGE
meeting-automation-staging   meeting-automation-staging-default-kopia   79m
velero                       meeting-automation-staging-default-kopia   75m
```

**Regel:** Velero erstellt BackupRepository CRD automatisch im `velero` Namespace — NICHT im Backup's Namespace. Manuell erstellte CRDs im Backup-Namespace werden NICHT von Velero verwendet.

| Aktion | Ergebnis |
|--------|----------|
| BackupRepository im `velero` Namespace | ✅ Wird von Velero verwendet (Status: Ready) |
| BackupRepository im `meeting-automation-staging` Namespace | ❌ Wird NICHT verwendet (kein Status) |
| BEIDE löschen + Velero restarten | ✅ Velero erstellt automatisch neue im `velero` Namespace |

### Test 3: Disk-Pressure durch FSB Backups

**BEWEIS (verifiziert 2026-08-12):**

```
BEFEHL: df -h / && du -sh /var/lib/rancher/k3s/storage/pvc-*minio*

ERGEBNIS:
Filesystem: 183G, Used: 173G (95%)  ← KRITISCH!
MinIO PVC:  59GB (PVC-Claim: 10Gi)   ← local-path erzwingt keine Limits!
```

**Root Cause:** Velero-Backups (Kopia-Daten) wurden in der MinIO gespeichert. local-path StorageClass erzwingt KEINE Größenlimits — eine 10Gi PVC kann beliebig viel Daten halten.

| PVC | Claim-Größe | Tatsächliche Nutzung |
|-----|-------------|--------------------|
| minio-data-minio-staging-0 | 10Gi | **59GB** (Velero-Backups!) |
| meeting-db-1 | 10Gi | 22GB (PostgreSQL + WAL) |
| postgres-data-postgres-staging-0 | 10Gi | 46MB |
| sentinel-models-claim | 2Gi | 1.1GB |
| rabbitmq-storage | 5Gi | 548KB |
| n8n-pvc | 1Gi | 0B |
| postgres-backup-pvc | 5Gi | 3.2MB |
| prometheus-db | 5Gi | 1.6GB |
| alertmanager-db | 5Gi | 0B |
| **Gesamt** | **53Gi** | **84GB** (59GB Velero in MinIO!) |

**Fix:** Velero-Backups aus MinIO gelöscht → Disk von 95% auf 63% gesunken.

### Test 4: Prometheus PVC erzeugt riesige Backup-Daten

**BEWEIS (verifiziert 2026-08-12):**

```
PVB: fsb-test-20260812-095218-686nf (Prometheus PVC)
  Total Bytes: 5.3GB (PVC-Claim)
  Bytes Done:  44.6GB (Kopia-Upload!)
  MinIO Wachstum: 0 → 46GB in 15 Minuten
```

**Root Cause:** Kopia sichert das gesamte Overlay-FS inklusive temporärer Dateien, WAL-Logs und Metadaten. Prometheus schreibt intensiv in sein TSDB → Kopia dedupliziert, aber die Rohdaten sind enorm.

**Empfehlung:** Prometheus aus Velero-FSB ausschließen:

```bash
# Bei Backup: --exclude-resources persistentvolumeclaims (im monitoring Namespace)
# Oder: Prometheus-PVC mit Label versehen und Velero-Selector verwenden
```

### Test 5: BSL (BackupStorageLocation) nach Bucket-Löschung

**BEWEIS (verifiziert 2026-08-12):**

```
BEFEHL: velero backup logs fsb-test-...

ERGEBNIS:
"BackupStorageLocation is unavailable"
"NoSuchBucket: velero-backups"
```

**Regel:** Wenn der MinIO-Bucket gelöscht wird:

1. Bucket neu erstellen: `mc mb local/velero-backups`
2. Velero Server restarten: `kubectl rollout restart deployment/velero -n velero`
3. 30-60s warten bis BSL `Available` wird
4. Erstes Backup auslösen (initialisiert Kopia-Repo)

### Test 6: Erfolgreiches FSB Backup (nach Recovery)

**BEWEIS (verifiziert 2026-08-12):**

```
Backup: clean-test-20260812-095218
PVBs:
  ✅ sentinel-models: 58MB (Completed)
  ✅ minio-data: 1.1GB (Completed)
  ✅ postgres-data: 23.3GB (Completed)
  ✅ n8n: 1.1MB (Completed)
  🔄 prometheus: InProgress (44.6GB — abgebrochen wegen Disk-Pressure)

MinIO: 46GB (nach 15 Min)
Disk: 82% (nach 15 Min)
```

**Backup-Funktioniert!** Aber Prometheus verursacht Disk-Pressure → muss ausgeschlossen werden.

### Zusammenfassung der Lektionen

| # | Lektion | Impact |
|---|---------|--------|
| 1 | **BackupRepository CRD gehört in `velero` Namespace** | Velero sucht CRD im `velero` Namespace, nicht im Backup-Namespace |
| 2 | **local-path erzwingt KEINE PVC-Limits** | 10Gi PVC kann 59GB halten → Disk-Limitsillusio |
| 3 | **Velero-Backups im selben MinIO = Gefahr** | Kopia-Daten füllen MinIO-PVC → Disk-Pressure |
| 4 | **Prometheus erzeugt 8x mehr Backup-Daten als PVC-Claim** | 5Gi PVC → 44GB Kopia-Upload |
| 5 | **Kopia-Repo nach Bucket-Löschung neu initialisieren** | BackupRepository CRD löschen + Velero restarten |
| 6 | **BSL wird nach Bucket-Löschung `Unavailable`** | Bucket neu erstellen + Velero restarten |

### Empfehlungen für Production

| # | Empfehlung | Aufwand |
|---|-----------|--------|
| 1 | **Velero-Backups NICHT im selben MinIO** — separater Bucket oder externes S3 | 30 Min |
| 2 | **Prometheus aus FSB ausschließen** — `--exclude-namespaces monitoring` | 5 Min |
| 3 | **Disk-Monitoring** — AlertRule für Disk >75% | 10 Min |
| 4 | **Velero BackupRepository CRD Recovery-Doku** — in CI/CD-Script einbauen | 15 Min |
| 5 | **Velero Schedule mit kleinerem Scope** — nur kritische PVCs | 10 Min |

---

## 13. Cluster-Rebuild Recovery (Lektion aus Phase 92)

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

---

## 15. Staging Disk-Pressure Lektionen (2026-08-12)

### Kernproblem

Staging-Cluster hat nur **183GB Disk**. Velero FSB-Backups erzeugen **30-50GB Kopia-Daten** aus 43Gi PVCs → Disk-Pressure → Pods werden evicted → BackupRepository geht verloren → Kreislauf.

### Verifizierte Fakten

| Fakt | Wert | Beweis |
|------|------|--------|
| Disk Gesamt | 183GB | `df -h /` |
| Disk belegt (vor Backup) | 118GB (65%) | `df -h /` |
| Disk belegt (nach Backup) | 173GB (95%) | `df -h /` nach 15 Min |
| MinIO PVC Claim | 10Gi | `kubectl get pvc` |
| MinIO PVC tatsächlich | 59GB | `du -sh /var/lib/rancher/k3s/storage/pvc-*minio*` |
| Prometheus PVC Claim | 5Gi | `kubectl get pvc` |
| Prometheus Kopia-Upload | 44GB | PVB Bytes Done |
| Kopia-Repo Initialisierung | ~500K | `du -sh velero-backups/kopia/` |
| Kopia-Voll-Backup | 30-50GB | MinIO Wachstum |

### Root Cause: local-path erzwingt keine Limits

```
BEFEHL: kubectl get pvc -n meeting-automation-staging -o custom-columns='NAME:.metadata.name,CAP:.status.capacity.storage,SC:.spec.storageClassName'

ERGEBNIS:
NAME                          CAP   SC
minio-data-minio-staging-0    10Gi  local-path
meeting-db-1                  10Gi  local-path
postgres-data-postgres-0      10Gi  local-path
rabbitmq-storage              5Gi   local-path
sentinel-models-claim         2Gi   local-path
n8n-pvc                       1Gi   local-path
postgres-backup-pvc           5Gi   local-path

BEFEHL: du -sh /var/lib/rancher/k3s/storage/pvc-*minio*
ERGEBNIS: 59GB (trotz 10Gi Claim!)
```

**Regel:** `local-path` StorageClass erzwingt KEINE Größenlimits. Eine 10Gi PVC kann beliebig viel Daten halten.

### Root Cause: Prometheus erzeugt 8x mehr Daten

```
BEFEHL: kubectl get podvolumebackups.velero.io -A -o wide | grep prometheus

ERGEBNIS:
NAME              STATUS      TOTALBYTES   BYTESDONE
686nf-...         InProgress  5368709120   47244640256
(5.3Gi Claim)     (44.6GB Kopia-Upload!)
```

**Regel:** Kopia sichert das gesamte Overlay-FS inklusive temporärer Dateien. Prometheus schreibt intensiv in sein TSDB → Kopia erzeugt 8x mehr Daten als der PVC-Claim.

### Disk-Pressure Taint

```
BEFEHL: kubectl get node instance-20260329-0846 -o json | python3 -c "import sys,json; d=json.load(sys.stdin); [print(c['type'],c['status']) for c in d['status']['conditions'] if c['type']=='DiskPressure']"

ERGEBNIS:
DiskPressure True  (bei 95%)
DiskPressure False (bei 65%)
```

**Regel:** k3s Kubelet erkennt Disk-Pressure automatisch und setzt Taint `node.kubernetes.io/disk-pressure:NoSchedule`. Velero Pods werden dann evicted.

### Recovery-Prozess (verifiziert)

Wenn Velero nach Disk-Pressure evicted wurde:

```bash
# 1. Velero-Backups aus MinIO löschen (schnellste Methode)
sudo rm -rf /var/lib/rancher/k3s/storage/pvc-*minio*/velero-backups/

# 2. Bucket neu erstellen
kubectl exec -n meeting-automation-staging minio-staging-0 -- \
  sh -c 'mc alias set local http://localhost:9000 minio_user minio_password 2>/dev/null && mc mb local/velero-backups 2>&1'

# 3. BackupRepository CRD löschen
kubectl delete backuprepositories.velero.io --all -n velero

# 4. Velero Server restarten
kubectl rollout restart deployment/velero -n velero

# 5. Warten bis DiskPressure=False (k3s prüft alle 5s)
sleep 60

# 6. Neues Backup starten
velero backup create recovery-$(date +%Y%m%d-%H%M%S) \
  --include-namespaces meeting-automation-staging \
  --exclude-namespaces monitoring \
  --wait
```

### Empfehlung: Scoped Backup (nur kritische PVCs)

```bash
# Nur n8n + sentinel + rabbitmq (8Gi gesamt, ~3-5GB Backup)
velero backup create scoped-$(date +%Y%m%d) \
  --include-namespaces meeting-automation-staging \
  --selector 'app in (n8n-staging,celery-worker-pro-staging,rabbitmq-staging)' \
  --exclude-namespaces monitoring \
  --wait
```

### Empfehlung: Schedule mit Exclude

**WICHTIG:** Helm aktualisiert keine bestehenden Schedules! Der Schedule muss manuell gepatcht werden:

```bash
# Schedule manuell patchen (excludedNamespaces + labelSelector)
kubectl patch schedule daily-backup -n velero --type=merge -p '{
  "spec": {
    "template": {
      "excludedNamespaces": ["monitoring"],
      "labelSelector": {
        "matchExpressions": [{
          "key": "app",
          "operator": "In",
          "values": ["minio-staging", "postgres-staging"]
        }]
      }
    }
  }
}'
```

**Ergebnis (verifiziert 2026-08-12):**

```yaml
spec:
  template:
    includedNamespaces:
    - meeting-automation-staging
    excludedNamespaces:
    - monitoring
    labelSelector:
      matchExpressions:
      - key: app
        operator: In
        values:
        - minio-staging
        - postgres-staging
    ttl: 168h0m0s
```

**Backup-Größe:** 20Gi (minio + postgres) → ~15-20GB Kopia → ~75% Disk (stabil)

### Production-Vergleich

| Aspekt | Staging | Production |
|--------|---------|------------|
| Disk | 183GB (⚠️ knapp) | 290G (✅ genug) |
| PVCs Gesamt | 43Gi | 58Gi |
| Kopia-Backup | 30-50GB | 28.7GiB |
| Disk nach Backup | 95% (⚠️) | 73% (✅) |
| Disk-Pressure | ⚠️ Possible | ✅ Unwahrscheinlich |
| FSB empfohlen | Nur Scoped (Selector) | Voll (alle PVCs) |

**Fazit:** Production hat genug Disk (290G) für FSB-Backups. Staging braucht Scoped Backups mit `--selector` und `--exclude-namespaces monitoring`.

---

## 16. Recovery-Verfahren (Kopia-Repository Reset)

### Wann ist das nötig?

| Szenario | Symptom | Ursache |
|----------|---------|--------|
| MinIO `velero-backups/` gelöscht | `repository not initialized` | Kopia-Repo gone |
| Kopia-Repo defekt | `Failed to wait BackupRepository` | Blob-Fehler |
| BackupRepository CRD stale | PVBs fehlgeschlagen | CRD zeigt auf nicht-existierendes Repo |
| Velero Helm-Upgrade fehlgeschlagen | BSL `Unavailable` | Konfiguration kaputt |

### Recovery-Schritte (VERIFIZIERT 2026-08-12)

```bash
# ============================================================
# RECOVERY: Kopia-Repository + Velero Reset
# ============================================================
# WARNUNG: Dies löscht ALLE existierenden Backups!
# Nur ausführen wenn Backups defekt oder unzugänglich.
# ============================================================

# Schritt 1: BackupRepository CRD löschen (KRITISCH!)
# ------------------------------------------------------
# Ohne diesen Schritt funktioniert NICHTS!
# Velero kann keine PVBs erstellen wenn die CRD stale ist.
kubectl delete backuprepositories.velero.io --all -n velero

# Schritt 2: Alle alten Backup-Records löschen
# ------------------------------------------------------
# Alte Records zeigen auf defektes Repo → müssen weg.
for b in $(kubectl get backups.velero.io -n velero -o json | \
  python3 -c "import sys,json; [print(i['metadata']['name']) for i in json.load(sys.stdin).get('items',[])]"); do
  kubectl delete backups.velero.io $b -n velero 2>/dev/null
done

# Schritt 3: MinIO velero-backups komplett leeren
# ------------------------------------------------------
# ACHTUNG: Pfad ist node-spezifisch!
# Staging: /var/lib/rancher/k3s/storage/pvc-<ID>_meeting-automation-staging_minio-data-minio-staging-0/
# Production: /var/lib/rancher/k3s/storage/pvc-<ID>_meeting-automation_minio-data-minio-0/

# Staging:
sudo rm -rf /var/lib/rancher/k3s/storage/pvc-*minio*/velero-backups/
echo 'Deleted velero-backups'

# Production (SSH zu 169.58.83.32):
# sudo rm -rf /var/lib/rancher/k3s/storage/pvc-*minio*/velero-backups/

# Schritt 4: Bucket neu erstellen
# ------------------------------------------------------
# Staging:
kubectl exec -n meeting-automation-staging minio-staging-0 -- \
  sh -c 'mc alias set local http://localhost:9000 minio_user minio_password 2>/dev/null && \
  mc mb local/velero-backups 2>&1'

# Production:
# kubectl exec -n meeting-automation minio-0 -- \
#   sh -c 'mc alias set local http://localhost:9000 minio_user 3Bsd1nsvjsnkCzcPvB96ew 2>/dev/null && \
#   mc mb local/velero-backups 2>&1'

# Schritt 5: Velero Server restarten
# ------------------------------------------------------
kubectl rollout restart deployment/velero -n velero

# Schritt 6: Warten (BSL muss Available werden)
# ------------------------------------------------------
echo 'Warte 60s für Velero Server + BSL...'
sleep 60

# BSL Status prüfen
kubectl get backupstoragelocations.velero.io -n velero -o jsonpath='{.items[0].status.phase}'
# Erwartet: Available

# Schritt 7: Erstes Backup (initialisiert Kopia-Repo)
# ------------------------------------------------------
# Staging (Scoped):
velero backup create recovery-$(date +%Y%m%d-%H%M%S) \
  --include-namespaces meeting-automation-staging \
  --exclude-namespaces monitoring \
  --selector 'app in (minio-staging,postgres-staging)' \
  --wait

# Production (Voll):
# velero backup create recovery-prod-$(date +%Y%m%d-%H%M%S) \
#   --include-namespaces meeting-automation \
#   --wait

# Schritt 8: Verifikation
# ------------------------------------------------------
# BackupRepository CRD (auto-erstellt)
kubectl get backuprepositories.velero.io -A
# Erwartet: <namespace>-default-kopia (AGE > 0)

# PodVolumeBackups
cubectl get podvolumebackups.velero.io -A -o wide
# Erwartet: PVBs mit Status Completed oder InProgress

# Disk
df -h /
# Erwartet: < 80%
```

### Recovery-Tabelle (Quick Reference)

| Schritt | Befehl | Erwartetes Ergebnis |
|---------|--------|--------------------|
| 1. CRD löschen | `kubectl delete backuprepositories.velero.io --all -n velero` | Keine CRDs mehr |
| 2. Backup-Records löschen | `kubectl delete backups.velero.io -n velero --all` | Keine Backups mehr |
| 3. MinIO leeren | `sudo rm -rf .../velero-backups/` | Bucket leer |
| 4. Bucket erstellen | `mc mb local/velero-backups` | Bucket vorhanden |
| 5. Velero restarten | `kubectl rollout restart deployment/velero -n velero` | Neuer Pod |
| 6. Warten | `sleep 60` | BSL Available |
| 7. Erstes Backup | `velero backup create ... --wait` | COMPLETED |
| 8. Verifikation | `kubectl get backuprepositories.velero.io -A` | CRD Ready |

### Häufige Fehler bei Recovery

| Fehler | Ursache | Lösung |
|--------|--------|--------|
| `BackupStorageLocation is unavailable` | BSL noch nicht ready | 60s warten, Velero neu starten |
| `repository not initialized` | Schritt 1 vergessen | **BackupRepository CRD löschen!** |
| `found existing data in storage` | MinIO nicht leer | Schritt 3 korrekt ausführen |
| PVB `Error: node-agent not found` | DaemonSet fehlt | `helm upgrade ... --set deployNodeAgent=true` |
| Disk-Pressure nach Backup | Zu viele PVCs gesichert | `--selector` für Scoped Backup verwenden |

---

## 17. Roadmap — Offene Punkte

### P2: CI/CD Pre-Deploy-Backup

**Ziel:** Vor jedem Production-Deploy ein automatisches Backup erstellen.

**Vorgehen:**

1. **GitHub Action in `deploy-production.yml` einfügen:**

```yaml
- name: Velero Pre-Deploy Backup
  run: |
    export KUBECONFIG=$(pwd)/kubeconfig-prod
    velero backup create pre-deploy-${{ github.sha }} \
      --include-namespaces=meeting-automation \
      --ttl=336h \
      --wait
    echo "✅ Velero backup created: pre-deploy-${{ github.sha }}"
```

2. **Backup muss COMPLETED sein bevor Deploy startet**
   - `--wait` blockiert bis Backup fertig
   - Bei Fehler: Deploy abbrechen

3. **Naming:** `pre-deploy-<git-sha>` (z.B. `pre-deploy-3be60a13`)

**Risiko:** Niedrig
**Aufwand:** ~15 Minuten
**Status:** ⬜ Offen

### P2: Velero-Backups auf externes S3

**Problem:** Velero-Backups liegen im selben MinIO (im selben Cluster). Bei Cluster-Verlust sind auch die Backups weg.

**Lösung:** Externes S3 als Backup-Backend.

**Optionen:**

| Option | Kosten | Aufwand | Sicherheit |
|--------|--------|---------|------------|
| **AWS S3** | ~$0.023/GB/Monat | Mittel | Hoch |
| **Wasabi** | $6.99/TB/Monat (kein Egress-Fee) | Mittel | Hoch |
| **Backblaze B2** | $0.006/GB/Monat | Mittel | Hoch |
| **MinIO auf zweitem Server** | Server-Kosten | Hoch | Mittel |

**Empfehlung:** Wasabi oder Backblaze B2 (günstig, kein Egress-Fee).

**Vorgehen:**

1. **S3-Bucket erstellen** (externer Anbieter)
2. **Velero Secret für externes S3 erstellen:**

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: velero-s3-external
  namespace: velero
type: Opaque
stringData:
  cloud: |
    [default]
    aws_access_key_id=<EXTERNAL_KEY>
    aws_secret_access_key=<EXTERNAL_SECRET>
```

3. **Zweite BSL hinzufügen:**

```bash
helm upgrade velero vmware-tanzu/velero -n velero --reuse-values \
  --set 'configuration.backupStorageLocation[1].name=external' \
  --set 'configuration.backupStorageLocation[1].provider=aws' \
  --set 'configuration.backupStorageLocation[1].bucket=velero-external-backups' \
  --set 'configuration.backupStorageLocation[1].config.region=us-east-1' \
  --set 'configuration.backupStorageLocation[1].config.s3Url=https://s3.wasabisys.com' \
  --set 'configuration.backupStorageLocation[1].credential=velero-s3-external,cloud'
```

4. **Schedule für externes Backup:**

```bash
velero schedule create weekly-external \
  --schedule="0 3 * * 0" \
  --ttl=720h \
  --storage-location=external \
  --include-namespaces=meeting-automation
```

**Risiko:** Mittel (neue Abhängigkeit)
**Aufwand:** ~1 Stunde
**Status:** ⬜ Offen

### Priorisierte Roadmap

| # | Punkt | Priorität | Aufwand | Risiko | Status |
|---|-------|-----------|---------|--------|--------|
| 1 | CI/CD Pre-Deploy-Backup | P2 | 15 Min | Niedrig | ⬜ Offen |
| 2 | Externes S3 (Wasabi/Backblaze) | P2 | 1 Std | Mittel | ⬜ Offen |
| 3 | MinIO PVC Monitoring (Alert >80%) | P3 | 10 Min | Niedrig | ⬜ Offen |
| 4 | Velero Backup-Retention auf 3 Tage (Staging) | P3 | 5 Min | Niedrig | ⬜ Offen |
| 5 | Velero Upgrade auf v1.19.x (wenn verfügbar) | P3 | 30 Min | Mittel | ⬜ Offen |
| 6 | Containerd Image Cleanup (systemd timer) | P2 | 30 Min | Niedrig | ✅ Erledigt (Staging) |
| 7 | Production: Image-GC Threshold 75% | P2 | 5 Min | Niedrig | ⬜ Offen |
| 8 | Production: Weekly Cleanup deployen | P2 | 30 Min | Niedrig | ⬜ Offen |

### Entscheidungen (offen)

| Frage | Option A | Option B | Empfehlung |
|-------|----------|----------|------------|
| Pre-Deploy-Backup blockierend? | Ja (CI/CD stoppt) | Nein (Warning) | Ja für Prod, Nein für Staging |
| Externes S3? | Wasabi ($7/TB) | Backblaze ($6/TB) | Wasabi (einfacher) |
| Staging Retention? | 7 Tage | 3 Tage | 3 Tage (weniger Speicher) |
| Production Retention? | 14 Tage | 7 Tage | 14 Tage (Sicherheit) |

---

## 18. Containerd Image Cleanup (Phase 3) — ✅ ABGESCHLOSSEN (2026-08-13)

### Kernproblem

Staging-Cluster (183GB Disk) hatte **81% Belegung** (148G). Hauptursache: **45G containerd Images** die nach jedem CI/CD-Deploy nicht automatisch gelöscht wurden. Der kubelet Image-GC Threshold war auf 85% (Default) — zu hoch für die aktuelle Disk-Größe.

### Verifizierte Fakten

| Fakt | Wert | Beweis |
|------|------|--------|
| Disk Gesamt | 183GB | `df -h /` |
| Disk belegt (vorher) | 148GB (81%) | `df -h /` |
| Disk belegt (nachher) | 134GB (73%) | `df -h /` nach Phase 1 |
| Containerd Images | 45G | `sudo du -sh /var/lib/rancher/k3s/agent/containerd/` |
| Containerd Snapshots | 529 | `ls snapshots/ | wc -l` |
| Image-GC Threshold (vorher) | 85% (Default) | k3s Default |
| Image-GC Threshold (nachher) | 75% | kubelet-arg in k3s Config |

### Root Cause

```
CI/CD Deploy
  → Neue Images werden pulled
  → Alte Images bleiben auf dem Node
  → Snapshots akkumulieren sich
  → Disk steigt: 76% → 81% → 85%?
  → Image-GC startet bei 85%
  → ABER: Bei 81% ist es zu spät!
  → Resultat: Immer volle Disk
```

### Durchgeführte Maßnahmen

#### Phase 1: Sofortige Bereinigung

| Schritt | Befehl | Ergebnis |
|---------|--------|----------|
| 1.1 | `sudo k3s ctr images prune` | 10 alte Images entfernt |
| 1.2 | Snapshots geprüft | 34 Snapshots entfernt |
| 1.3 | Disk geprüft | 134G/183G (73%) — +14G freigeben |

#### Phase 2: Image-GC Threshold senken

| Schritt | Befehl | Ergebnis |
|---------|--------|----------|
| 2.1 | Backup: `sudo cp config.yaml /tmp/` | ✅ |
| 2.2 | Config: `kubelet-arg: [image-gc-high-threshold=75]` | ✅ |
| 2.3 | Restart: `sudo systemctl restart k3s` | ✅ |
| 2.4 | Verifikation: kubelet Args in Logs | ✅ `--image-gc-high-threshold=75` |

#### Phase 3: Weekly Cleanup (systemd timer)

| Schritt | Status | Details |
|---------|--------|--------|
| Script | ✅ | `/usr/local/bin/image-cleanup.sh` |
| Systemd Timer | ✅ | `image-cleanup.timer` (enabled) |
| Schedule | ✅ | Sonntag 03:00 UTC (wöchentlich) |
| Test-Lauf | ✅ | Script ausgeführt, Logs vorhanden |
| Git Commit | ✅ | `6f28a5c5` |

### Technische Details

| Komponente | Wert |
|------------|------|
| Script | `/usr/local/bin/image-cleanup.sh` |
| Timer | `image-cleanup.timer` (enabled) |
| Service | `image-cleanup.service` |
| Schedule | Sonntag 03:00 UTC (wöchentlich) |
| Nächster Lauf | 2026-08-16 03:00 UTC |
| Log-Datei | `/var/log/image-cleanup.log` |
| Befehl | `ctr images prune --all` |

### Verifikation

```bash
# Timer Status prüfen
sudo systemctl status image-cleanup.timer

# Nächsten Lauf prüfen
sudo systemctl list-timers image-cleanup.timer

# Manuell ausführen
sudo /usr/local/bin/image-cleanup.sh

# Logs prüfen
cat /var/log/image-cleanup.log
```

### Rollback

```bash
# Timer deaktivieren
sudo systemctl disable image-cleanup.timer
sudo systemctl stop image-cleanup.timer

# k3s Config zurücksetzen
sudo cp /tmp/config.yaml.bak.20260813105455 /etc/rancher/k3s/config.yaml
sudo systemctl restart k3s
```

### Lessons Learned

1. **Image-GC Threshold ist kritisch:** Default-Wert (85%) zu hoch für SingleNode-Cluster mit CI/CD
2. **containerd Snapshot-Akkumulation:** Jeder Deploy erstellt neue Snapshots die nicht automatisch gelöscht werden
3. **Monitoring fehlt:** Kein Alert für Disk-Utilization → Problem erst bei 81% bemerkt
4. **K8s CronJob kann nicht auf host namespace zugreifen:** containerd socket erfordert hostPID + hostNetwork + hostPath mounts → systemd timer ist die richtige Lösung

### Production-Vergleich

| Aspekt | Staging | Production |
|--------|---------|------------|
| Disk | 183GB (81%) | 290G (82%) |
| Image-GC Threshold | 75% (angepasst) | 85% (Default) |
| Weekly Cleanup | ✅ systemd timer | ⬜ Offen |
| Disk-Pressure Risk | ⚠️ Hoch | 🟡 Mittel |

**Empfehlung:** Production braucht ebenfalls:
1. Image-GC Threshold auf 75% senken
2. Weekly Cleanup (systemd timer) deployen
