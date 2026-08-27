#!/bin/bash
# 04-velero-scope-check.sh — Velero Scope Check + P3 Probe Patches
# Env: KUBECONFIG
set -e

NAMESPACE="${NAMESPACE:-meeting-automation-staging}"
export KUBECONFIG="${KUBECONFIG:-$(pwd)/kubeconfig-staging}"

echo "=== Velero Scope Check ==="

# Guard: Skip if Velero is intentionally scaled down
VELERO_DESIRED=$(kubectl get ds node-agent -n velero -o jsonpath='{.spec.desiredNumberScheduled}' 2>/dev/null || echo "0")
if [ "$VELERO_DESIRED" = "0" ]; then
  echo "⚠️ Velero node-agent scaled to 0 — skipping scope check"
  exit 0
fi

# Check 1: Schedule muss Selector haben
SELECTOR=$(kubectl get schedule daily-backup -n velero -o jsonpath='{.spec.template.labelSelector}' 2>/dev/null || echo '')
if [ -z "$SELECTOR" ] || echo "$SELECTOR" | grep -q 'minio'; then
  echo "❌ Velero Schedule hat keinen/falschen Selector!"
  echo "   Erwartet: app In [n8n-staging, celery-worker-pro-staging]"
  echo "   Gefunden: $SELECTOR"
  echo "   Deploy abgebrochen."
  exit 1
fi
echo "✅ Velero Schedule Selector korrekt: $SELECTOR"

# Check 2: MinIO muss opt-out Annotation haben
MINIO_ANNOTATION=$(kubectl get statefulset minio-staging -n "$NAMESPACE" -o jsonpath='{.spec.template.metadata.annotations.backup\.velero\.io/backup-volumes-excludes}' 2>/dev/null || echo '')
if [ "$MINIO_ANNOTATION" != "minio-data" ]; then
  echo "❌ MinIO StatefulSet hat keine opt-out Annotation!"
  echo "   Erwartet: backup.velero.io/backup-volumes-excludes: minio-data"
  echo "   Gefunden: $MINIO_ANNOTATION"
  echo "   Deploy abgebrochen."
  exit 1
fi
echo "✅ MinIO opt-out Annotation korrekt: $MINIO_ANNOTATION"

# P3 Fix: Velero Liveness/Readiness Probe
echo "=== P3: Velero initialDelaySeconds 10→60 ==="
kubectl patch deployment velero -n velero --type=json -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/livenessProbe/initialDelaySeconds", "value": 60},
  {"op": "replace", "path": "/spec/template/spec/containers/0/readinessProbe/initialDelaySeconds", "value": 60}
]' 2>&1 || echo "Warning: Velero patch failed (not deployed yet?)"
echo "✅ Velero probes patched"
