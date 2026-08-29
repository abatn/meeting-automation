#!/bin/bash
# Velero Installation für Meeting Automation Staging
# Voraussetzung: MinIO läuft bereits im Cluster

set -e

NAMESPACE="meeting-automation-staging"
VELERO_VERSION="v1.14.0"

echo "=== Velero Installation ==="

# 1. Velero CLI installieren (falls nicht vorhanden)
if ! command -v velero &> /dev/null; then
    echo "Installing Velero CLI..."
    wget -q https://github.com/vmware-tanzu/velero/releases/download/${VELERO_VERSION}/velero-${VELERO_VERSION}-linux-arm64.tar.gz
    tar xzf velero-${VELERO_VERSION}-linux-arm64.tar.gz
    sudo mv velero-${VELERO_VERSION}-linux-arm64/velero /usr/local/bin/
    rm -rf velero-${VELERO_VERSION}-linux-arm64*
fi

echo "Velero CLI: $(velero version --client-only)"

# 2. MinIO Credentials für Velero
cat > /tmp/credentials-velero <<EOF
[default]
aws_access_key_id = minio_user
aws_secret_access_key = minio_password
EOF

# 3. Velero installieren
velero install \
  --provider aws \
  --bucket velero-backups \
  --secret-file /tmp/credentials-velero \
  --backup-location-config \
    region=minio,s3ForcePathStyle="true",s3Url=http://minio-staging.${NAMESPACE}.svc.cluster.local:9000 \
  --plugins velero/velero-plugin-for-aws:v1.9.2 \
  --use-volume-snapshots=false \
  --wait

# 4. Backup-Schedule erstellen (täglich 2 Uhr)
velero schedule create daily-backup \
  --schedule="0 2 * * *" \
  --include-namespaces ${NAMESPACE} \
  --ttl 720h

# 5. Erstes Backup erstellen
velero backup create initial-backup-$(date +%Y%m%d) \
  --include-namespaces ${NAMESPACE}

echo "=== Velero Installation abgeschlossen ==="
echo "Backup-Schedule: daily-backup (täglich 2 Uhr)"
echo "Backup-Liste: velero backup get"
echo "Backup-Details: velero backup describe daily-backup --details"
