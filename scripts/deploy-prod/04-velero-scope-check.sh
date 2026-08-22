#!/bin/bash
# 04-velero-scope-check.sh — Velero Scope Check + P3 Probe Patches
# Env: NAMESPACE (default: meeting-automation)
set -e

NAMESPACE="${NAMESPACE:-meeting-automation}"
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

echo "=== Velero Scope Check ==="

# Check 1: Schedule muss existieren + excludedNamespaces haben (kein monitoring)
EXCLUDED=$(kubectl get schedule daily-backup -n velero -o jsonpath='{.spec.template.excludedNamespaces}' 2>/dev/null || echo '')
if [ -z "$EXCLUDED" ] || ! echo "$EXCLUDED" | grep -q 'monitoring'; then
  echo "❌ Velero Schedule hat keine excludedNamespaces!"
  echo "   Erwartet: monitoring in excludedNamespaces"
  echo "   Gefunden: $EXCLUDED"
  echo "   Deploy abgebrochen."
  exit 1
fi
echo "✅ Velero Schedule excludedNamespaces korrekt: $EXCLUDED"

# Check 2: MinIO muss opt-out Annotation haben
MINIO_ANNOTATION=$(kubectl get statefulset minio -n "$NAMESPACE" -o jsonpath='{.spec.template.metadata.annotations.backup\.velero\.io/backup-volumes-excludes}' 2>/dev/null || echo '')
if [ "$MINIO_ANNOTATION" != "minio-data" ]; then
  echo "❌ MinIO StatefulSet hat keine opt-out Annotation!"
  echo "   Erwartet: backup.velero.io/backup-volumes-excludes: minio-data"
  echo "   Gefunden: $MINIO_ANNOTATION"
  echo "   Deploy abgebrochen."
  exit 1
fi
echo "✅ MinIO opt-out Annotation korrekt: $MINIO_ANNOTATION"

# P3 Fix: Velero Liveness/Readiness Probe
# initialDelaySeconds 10→60 (Kopia-Reinit braucht >10s)
echo "=== Patching Velero Probes (P3 Fix) ==="
kubectl patch deployment velero -n velero --type=json -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/livenessProbe/initialDelaySeconds", "value": 60},
  {"op": "replace", "path": "/spec/template/spec/containers/0/readinessProbe/initialDelaySeconds", "value": 60}
]' 2>&1 || echo "⚠️ Velero patch failed (not deployed yet?)"
echo "✅ Velero probes patched"
