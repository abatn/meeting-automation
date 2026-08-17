#!/bin/bash
# 03-deploy-manifests.sh — Apply all staging manifests (exclude Helm values + old LiveKit + HPA)
# Env: KUBECONFIG
set -e

NAMESPACE="${NAMESPACE:-meeting-automation-staging}"
export KUBECONFIG="${KUBECONFIG:-$(pwd)/kubeconfig-staging}"

echo "=== Deploy All Staging Resources ==="
for f in infrastructure/kubernetes/staging/*.yaml; do
  fname=$(basename "$f")
  # Skip Helm values (livekit-server-values.yaml, egress-values.yaml)
  [[ "$fname" == *values*.yaml ]] && continue
  # Skip old LiveKit deployment YAMLs (Helm-managed now)
  [[ "$fname" == *livekit-*-deployment.yaml ]] && continue
  # Skip hardcoded HPA (replaced by KEDA ScaledObjects)
  [[ "$fname" == *hpa*.yaml ]] && continue
  echo "Applying: $fname"
  kubectl apply -f "$f" -n "$NAMESPACE" || echo "Warning: Failed to apply $fname"
done
kubectl rollout restart deployment/onlyoffice-staging -n "$NAMESPACE" 2>&1 || echo "Warning: OnlyOffice restart failed"

# Restart StatefulSets (probes may have changed — kubectl apply alone doesn't roll them out)
echo "Restarting StatefulSets (RabbitMQ, MinIO, Postgres)..."
for STS in rabbitmq-staging minio-staging postgres-staging meeting-db; do
  if kubectl get statefulset "$STS" -n "$NAMESPACE" &>/dev/null; then
    echo "  Restarting $STS..."
    kubectl rollout restart statefulset/"$STS" -n "$NAMESPACE"
  fi
done
echo "Waiting 30s for StatefulSet rollouts..."
sleep 30
for STS in rabbitmq-staging minio-staging postgres-staging meeting-db; do
  if kubectl get statefulset "$STS" -n "$NAMESPACE" &>/dev/null; then
    kubectl rollout status statefulset/"$STS" -n "$NAMESPACE" --timeout=120s || echo "⚠️ $STS rollout timed out"
  fi
done
echo "✅ All staging manifests applied + StatefulSets restarted"
