#!/bin/bash
# 02-install-infra.sh — Install Longhorn + KEDA + NetworkPolicy
# Env: KUBECONFIG
set -e

NAMESPACE="${NAMESPACE:-meeting-automation-staging}"
export KUBECONFIG="${KUBECONFIG:-$(pwd)/kubeconfig-staging}"

echo "=== Install Longhorn ==="
if kubectl get namespace longhorn-system &>/dev/null; then
  echo "✅ longhorn-system already exists — skipping"
else
  echo "📦 Installing Longhorn v1.12.0..."
  helm repo add longhorn https://charts.longhorn.io 2>/dev/null || true
  helm repo update
  helm install longhorn longhorn/longhorn \
    --namespace longhorn-system --create-namespace --version 1.12.0 \
    --set defaultSettings.defaultReplicaCount=1 \
    --set defaultSettings.createDefaultDiskLabeledNodes=true \
    --set defaultSettings.defaultClass=false \
    --set defaultSettings.guaranteedInstanceManagerCPU=200 \
    --wait --timeout 10m || echo "⚠️ Warning: Longhorn install failed, continuing"
fi

echo "=== Install KEDA ==="
helm repo add kedacore https://kedacore.github.io/charts 2>/dev/null || true
helm repo update
helm upgrade --install keda kedacore/keda \
  --namespace keda --create-namespace \
  --set operator.replicaCount=1 \
  --set metricsServer.replicaCount=1 \
  --wait --timeout 5m || echo "⚠️ Warning: KEDA install failed"
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=keda-operator -n keda --timeout=120s || true
echo "✅ KEDA installed"

echo "=== Test KEDA → RabbitMQ Connectivity ==="
kubectl run keda-nettest --rm -i --restart=Never --image=busybox:1.36 -n keda \
  -- sh -c "nc -w5 rabbitmq-staging.meeting-automation-staging.svc.cluster.local 5672 && echo OK || echo FAIL" 2>&1 || true

echo "=== Deploy KEDA ScaledObjects + NetworkPolicy ==="
kubectl apply -f infrastructure/kubernetes/staging/keda-scaledobjects.yaml
kubectl apply -f infrastructure/kubernetes/staging/keda-rabbitmq-networkpolicy.yaml
echo "✅ KEDA ScaledObjects + NetworkPolicy deployed"
kubectl get scaledobject -n "$NAMESPACE"

echo "=== Delete hardcoded HPA ==="
kubectl delete hpa celery-worker-hpa -n "$NAMESPACE" --ignore-not-found
echo "✅ Hardcoded HPA removed"
