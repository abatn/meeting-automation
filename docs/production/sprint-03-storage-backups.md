# Sprint 3: Storage + PostgreSQL HA + Backups

> **Dauer:** ~2 Wochen | **Status:** ⬜ Offen
> **Komponenten:** Longhorn (CNCF), CloudNativePG (CNCF), Velero (CNCF), MinIO (open source)

## Storage: Longhorn

### Installation

```bash
# Longhorn installieren
helm repo add longhorn https://charts.longhorn.io
helm upgrade --install longhorn longhorn/longhorn \
  --namespace longhorn-system --create-namespace

# Als Default StorageClass setzen
kubectl annotate storageclass longhorn storageclass.kubernetes.io/is-default-class=true \
  --overwrite

# UI zugänglich machen
kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80
# URL: http://localhost:8080
```

### Migration von hostpath zu Longhorn

Aktuell nutzen alle PVCs `local-path` (hostpath). Migration zu Longhorn:

```bash
# 1. StorageClass auf Longhorn umstellen
kubectl patch storageclass local-path -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'

# 2. Bestehende PVCs löschen (Daten in Longhorn neu)
kubectl delete pvc -n meeting-automation --all

# 3. Neuer PVC mit Longhorn
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data
  namespace: meeting-automation
spec:
  storageClassName: longhorn
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
EOF

# 4. Pods neustarten (nehmen neuen PVC)
kubectl rollout restart statefulset -n meeting-automation postgres
kubectl rollout restart deployment -n meeting-automation
```

### Alternativ: Rook/Ceph

```bash
# Für fortgeschrittene Storage-Anforderungen
helm repo add rook-release https://charts.rook.io/release
helm upgrade --install rook-ceph rook-release/rook-ceph \
  --namespace rook-ceph --create-namespace
```

## PostgreSQL HA: CloudNativePG

### Installation

```bash
# Operator installieren
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm upgrade --install cnpg cnpg/cloudnative-pg \
  --namespace cnpg-system --create-namespace
```

### Cluster-Definition

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: meeting-db
  namespace: meeting-automation
spec:
  instances: 3
  storage:
    size: 10Gi
    storageClass: longhorn
  bootstrap:
    initdb:
      database: meeting_db
      owner: meeting_user
      secret:
        name: postgres-secrets
  postgresql:
    parameters:
      max_connections: "200"
      shared_buffers: "128MB"
  backup:
    barmanObjectStore:
      destinationPath: s3://backups/postgres/
      endpointURL: http://minio:9000
      s3Credentials:
        accessKeyId:
          name: minio-credentials
          key: access-key
        secretAccessKey:
          name: minio-credentials
          key: secret-key
    retentionPolicy: "30d"
  monitoring:
    enablePodMonitor: true
```

### Migration von statefulset zu CloudNativePG

```bash
# 1. Bestehenden PostgreSQL-StatefulSet sichern
kubectl exec -n meeting-automation postgres-0 -- pg_dump -U meeting_user meeting_db > backup.sql

# 2. StatefulSet entfernen
kubectl delete statefulset postgres -n meeting-automation

# 3. Neuen CNPG-Cluster deployen
kubectl apply -f cnpg-cluster.yaml

# 4. Daten importieren
kubectl exec -n meeting-automation -it meeting-db-1 -- psql -U meeting_user meeting_db < backup.sql
```

## Backups: Velero + MinIO

MinIO läuft bereits im Cluster — nutze es als S3-kompatibles Backup-Ziel!

### Velero installieren

```bash
# Credentials für MinIO erstellen
cat > credentials-velero <<EOF
[default]
aws_access_key_id = minio_user
aws_secret_access_key = minio_password_prod
EOF

# Velero installieren
velero install \
  --provider aws \
  --bucket velero-backups \
  --secret-file ./credentials-velero \
  --backup-location-config \
    region=minio,s3ForcePathStyle="true",s3Url=http://minio:9000 \
  --plugins velero/velero-plugin-for-aws:v1.0.0 \
  --use-volume-snapshots=false
```

### Backup-Schedule

```bash
# Tägliches Backup (2 Uhr nachts)
velero schedule create daily-backup \
  --schedule="0 2 * * *" \
  --include-namespaces meeting-automation \
  --ttl 720h

# Manuelles Backup
velero backup create manual-backup-$(date +%Y%m%d) \
  --include-namespaces meeting-automation

# Backup-Liste
velero backup get
```

### Postgres DB-Dump (Alternative)

```bash
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: meeting-automation
spec:
  schedule: "0 3 * * *"
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
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
            - PGPASSWORD=\$POSTGRES_PASSWORD pg_dump -h postgres -U meeting_user meeting_db | gzip > /backup/meeting_db-\$(date +%Y%m%d-%H%M%S).sql.gz
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

# PVC für Backups
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-backup-pvc
  namespace: meeting-automation
spec:
  storageClassName: longhorn
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
EOF
```

### Restore

```bash
# Velero Restore (kompletter Namespace)
velero restore create --from-backup daily-backup-20260527

# PostgreSQL Restore (einzelner Dump)
# Backup-Datei in den Pod kopieren
kubectl cp backup.sql meeting-automation/meeting-db-1:/tmp/
# DB restored
kubectl exec -n meeting-automation meeting-db-1 -- \
  psql -U meeting_user meeting_db < /tmp/backup.sql
```

## Validation

```bash
# Longhorn UI
kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80
# → http://localhost:8080

# Velero Backup-Status
velero backup get
velero backup describe daily-backup --details

# PostgreSQL HA testen
kubectl exec -n meeting-automation -it meeting-db-1 -- pg_isready
kubectl delete pod -n meeting-automation meeting-db-1
# → Neuer Pod wird automatisch erstellt (Operator)
```
