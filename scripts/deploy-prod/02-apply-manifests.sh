#!/bin/bash
# 02-apply-manifests.sh — Apply Kubernetes manifests
# Env: MANIFESTS_DIR (default: /root/production-manifests)
set -e

MANIFESTS_DIR="${MANIFESTS_DIR:-/root/production-manifests}"
cd "$MANIFESTS_DIR"

echo "=== Applying manifests ==="
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

kubectl apply -f namespace.yaml

# Secrets: Only apply if they don't exist (manual update required for changes)
for secret in backend-secrets postgres-secrets redis-secrets minio-secrets rabbitmq-secrets livekit-secrets n8n-secrets; do
  kubectl get secret "$secret" -n meeting-automation >/dev/null 2>&1 || \
    kubectl apply -f "${secret}.yaml" -n meeting-automation
done

kubectl apply -f backend-config.yaml -f livekit-configmap.yaml -f livekit-egress-configmap.yaml -f frontend-nginx-config.yaml
kubectl apply -f redis-deployment.yaml -f rabbitmq-statefulset.yaml -f minio-statefulset.yaml
kubectl apply -f cnpg-cluster.yaml
kubectl apply --server-side -f cnpg-scheduled-backup.yaml 2>/dev/null || echo "⚠️ ScheduledBackup already exists or CRD missing"
kubectl apply -f backend-deployment.yaml -f frontend-deployment.yaml -f onlyoffice-deployment.yaml -f n8n-deployment.yaml
kubectl apply -f celery-worker-deployment.yaml -f celery-worker-pro-deployment.yaml -f celery-beat-deployment.yaml
kubectl apply -f network-policies.yaml
kubectl apply -f ingress-prod.yaml
kubectl apply -f n8n-ingress.yaml

# Operator-Patches (widerstehen Helm-Upgrade/CI-Deploy Verlust)
# CNPG Operator — nur anwenden wenn Deployment existiert
if kubectl get deployment cnpg-cloudnative-pg -n cnpg-system &>/dev/null; then
  kubectl apply -f cnpg-operator-patch.yaml 2>/dev/null || echo "⚠️ CNPG Operator patch failed (container name may have changed)"
else
  echo "⚠️ CNPG Operator deployment not found — skipping patch"
fi

# Longhorn Settings — nur anwenden wenn CRD existiert
if kubectl get crd settings.longhorn.io &>/dev/null; then
  kubectl apply -f longhorn-settings-patch.yaml 2>/dev/null || echo "⚠️ Longhorn Settings patch failed (CRD may have changed)"
else
  echo "⚠️ Longhorn Settings CRD not found — skipping patch"
fi

echo "✅ Manifests applied"

# Post-Deploy Verifikation der Operator-Patches
echo ""
echo "=== Verifikation: Operator-Patches + ScheduledBackup ==="

# CNPG ScheduledBackup — prüfe ob ScheduledBackup existiert
if kubectl get scheduledbackup daily-backup -n meeting-automation &>/dev/null; then
  SCHED=$(kubectl get scheduledbackup daily-backup -n meeting-automation -o jsonpath='{.spec.schedule}' 2>/dev/null)
  echo "  ✅ CNPG ScheduledBackup: schedule=$SCHED"
else
  echo "  ⚠️ CNPG ScheduledBackup not found"
fi

# CNPG Operator — max-concurrent-reconciles prüfen (dynamisch, kein hardcoded Index)
if kubectl get deployment cnpg-cloudnative-pg -n cnpg-system &>/dev/null; then
  CNPG_ALL_ARGS=$(kubectl get deploy -n cnpg-system cnpg-cloudnative-pg -o jsonpath='{.spec.template.spec.containers[0].args}' 2>/dev/null || echo "[]")
  if echo "$CNPG_ALL_ARGS" | grep -q "max-concurrent-reconciles=2"; then
    echo "  ✅ CNPG Operator: max-concurrent-reconciles=2"
  else
    echo "  ⚠️ CNPG Operator: max-concurrent-reconciles=2 not found in args: $CNPG_ALL_ARGS"
  fi
else
  echo "  ⚠️ CNPG Operator deployment not found — verification skipped"
fi

# Longhorn Settings — 5 Werte prüfen
if kubectl get crd settings.longhorn.io &>/dev/null; then
  LH_ERRORS=0
  for setting in upgrade-checker kubernetes-metrics-server-metrics-enabled backup-concurrent-limit restore-concurrent-limit snapshot-heavy-task-concurrent-limit; do
    value=$(kubectl get settings.longhorn.io "$setting" -n longhorn-system -o jsonpath='{.value}' 2>/dev/null || echo "NOT_FOUND")
    case "$setting" in
      upgrade-checker)                           expected="false" ;;
      kubernetes-metrics-server-metrics-enabled) expected="false" ;;
      backup-concurrent-limit)                   expected="1" ;;
      restore-concurrent-limit)                  expected="1" ;;
      snapshot-heavy-task-concurrent-limit)      expected="1" ;;
    esac
    if [ "$value" = "$expected" ]; then
      echo "  ✅ Longhorn $setting: $value"
    else
      echo "  ⚠️ Longhorn $setting: expected=$expected got=$value"
      LH_ERRORS=$((LH_ERRORS + 1))
    fi
  done
  if [ "$LH_ERRORS" -gt 0 ]; then
    echo "  ⚠️ $LH_ERRORS Longhorn setting(s) have unexpected values"
  fi
else
  echo "  ⚠️ Longhorn CRD not found — verification skipped"
fi
