#!/bin/bash
# 03-deploy-livekit.sh — Deploy LiveKit Server + Egress via Helm
# Env: MANIFESTS_DIR (default: /root/production-manifests), NAMESPACE (default: meeting-automation)
set -e

MANIFESTS_DIR="${MANIFESTS_DIR:-/root/production-manifests}"
NAMESPACE="${NAMESPACE:-meeting-automation}"
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

echo "=== Deploying LiveKit via Helm ==="

# LiveKit Server via Helm
echo "--- LiveKit Server ---"
helm upgrade --install livekit-server "$MANIFESTS_DIR/charts/livekit-server-1.9.0.tgz" \
  -n "$NAMESPACE" \
  --values "$MANIFESTS_DIR/livekit-server-values.yaml" \
  --wait --timeout 10m || echo "⚠️ Warning: LiveKit Server Helm upgrade failed"

# hostNetwork + Probes Patch (P4 Fix)
kubectl patch deployment livekit-server -n "$NAMESPACE" --type='json' \
  -p='[
    {"op":"add","path":"/spec/template/spec/hostNetwork","value":true},
    {"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"},
    {"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/initialDelaySeconds","value":30},
    {"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/timeoutSeconds","value":3},
    {"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/failureThreshold","value":3},
    {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/initialDelaySeconds","value":10},
    {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/timeoutSeconds","value":3},
    {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/failureThreshold","value":3}
  ]' 2>/dev/null || true
kubectl rollout restart deployment/livekit-server -n "$NAMESPACE" 2>/dev/null || true

# LiveKit Egress via Helm
echo "--- LiveKit Egress ---"
helm upgrade --install livekit-egress "$MANIFESTS_DIR/charts/egress-1.8.4.tgz" \
  -n "$NAMESPACE" \
  --values "$MANIFESTS_DIR/egress-values.yaml" \
  --wait --timeout 10m || echo "⚠️ Warning: LiveKit Egress Helm upgrade failed"

# hostNetwork + Recreate Strategy Patch
kubectl patch deployment livekit-egress -n "$NAMESPACE" --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/hostNetwork","value":true},{"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"},{"op":"replace","path":"/spec/strategy","value":{"type":"Recreate"}}]' 2>/dev/null || true
kubectl rollout restart deployment/livekit-egress -n "$NAMESPACE" 2>/dev/null || true

echo "✅ LiveKit deployed via Helm"
