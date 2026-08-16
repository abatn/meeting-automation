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
echo "✅ All staging manifests applied"
