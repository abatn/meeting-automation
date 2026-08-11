#!/bin/bash
# Velero Installation für Meeting Automation Staging
# Installiert via Helm (v12.1.0, App v1.18.1)
# Voraussetzung: MinIO läuft bereits im Cluster
#
# AKTUELLER STAND (2026-08-11):
#   - Velero v1.18.1 via Helm v12.1.0
#   - Kopia als Uploader (nicht Restic)
#   - --default-volumes-to-fs-backup aktiviert
#   - BackupRepository: meeting-automation-staging-default-kopia
#   - Schedule: daily-backup (0 2 * * *)
#
# WARNUNG: Dieses Script ist VERALTET und nur als Referenz!
# Aktuelle Installation via:
#   helm upgrade velero vmware-tanzu/velero -n velero -f velero-values.yaml --install

set -e

NAMESPACE="meeting-automation-staging"

echo "=== Velero Installation (Helm-basiert) ==="

# 1. Helm Repository hinzufügen
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts 2>/dev/null || true
helm repo update

# 2. Velero Credentials Secret erstellen
kubectl create secret generic velero-s3-credentials \
  -n velero \
  --from-literal=cloud='[default]
aws_access_key_id = minio_user
aws_secret_access_key = minio_password' \
  --dry-run=client -o yaml | kubectl apply -f -

# 3. Velero via Helm installieren/upgraden
helm upgrade velero vmware-tanzu/velero \
  -n velero \
  -f velero-values.yaml \
  --install \
  --wait

# 4. BackupRepository CRD prüfen (wird automatisch erstellt)
echo "Warte 30s für Repository-Init..."
sleep 30
REPO_PHASE=$(kubectl get backuprepositories.velero.io meeting-automation-staging-default-kopia \
  -n velero -o jsonpath='{.status.phase}' 2>/dev/null || echo "nicht vorhanden")
echo "BackupRepository Phase: $REPO_PHASE"

# 5. Falls nicht vorhanden: Manuell erstellen
if [ "$REPO_PHASE" != "Ready" ]; then
  echo "Erstelle BackupRepository CRD..."
  kubectl apply -f velero-backup-repository.yaml
fi

echo "=== Velero Installation abgeschlossen ==="
echo "Version: velero version"
echo "Backups: velero backup get"
echo "Repository: kubectl get backuprepositories.velero.io -n velero"
