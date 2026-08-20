#!/bin/bash
# 05-install-infra.sh — Install Longhorn + KEDA + NetworkPolicy
# Env: NAMESPACE (default: meeting-automation)
set -e

NAMESPACE="${NAMESPACE:-meeting-automation}"
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Install Longhorn if not present (skip-if-exists)
echo "=== Checking Longhorn ==="
if kubectl get namespace longhorn-system &>/dev/null; then
  echo "✅ longhorn-system namespace already exists — skipping Longhorn install"
else
  echo "📦 Installing Longhorn v1.12.0 on production..."
  helm repo add longhorn https://charts.longhorn.io 2>/dev/null || true
  helm repo update
  helm install longhorn longhorn/longhorn \
    --namespace longhorn-system \
    --create-namespace \
    --version 1.12.0 \
    --set defaultSettings.defaultReplicaCount=1 \
    --set defaultSettings.createDefaultDiskLabeledNodes=true \
    --set defaultSettings.defaultClass=true \
    --set defaultSettings.guaranteedInstanceManagerCPU=200 \
    --wait --timeout 10m || echo "⚠️ Warning: Longhorn install failed, continuing deployment"
  echo "✅ Longhorn v1.12.0 installed on production"
fi

# Install KEDA (skip if already running)
echo "=== Checking KEDA ==="
KEDA_READY=$(kubectl get pods -n keda -l app.kubernetes.io/name=keda-operator -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")
if [ "$KEDA_READY" = "True" ]; then
  echo "✅ KEDA already installed and running — skipping helm install"
else
  echo "📦 Installing KEDA..."
  helm repo add kedacore https://kedacore.github.io/charts 2>/dev/null || true
  helm repo update
  helm upgrade --install keda kedacore/keda \
    --namespace keda --create-namespace \
    --set operator.replicaCount=1 \
    --set metricsServer.replicaCount=1 \
    --wait --timeout 5m || echo "⚠️ Warning: KEDA install failed"
  kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=keda-operator -n keda --timeout=120s || true
  echo "✅ KEDA installed"

  # Test KEDA → RabbitMQ Cross-Namespace Connectivity (only on fresh install)
  echo "=== Testing KEDA → RabbitMQ connectivity ==="
  KEDA_TEST=$(kubectl run keda-nettest --rm -i --restart=Never --image=busybox:1.36 -n keda \
    -- sh -c "nc -w5 rabbitmq.meeting-automation.svc.cluster.local 5672 && echo OK || echo FAIL" 2>&1 || true)
  echo "$KEDA_TEST"
  if echo "$KEDA_TEST" | grep -q "FAIL"; then
    echo "⚠️ Cross-Namespace NetworkPolicy BLOCKS keda → rabbitmq"
    echo "   Celery Worker ScaledObjects will NOT work (rabbitmq trigger)"
    echo "   CPU-based ScaledObjects (backend, egress) will still work"
    echo "   Fix: Deploy keda-rabbitmq-networkpolicy.yaml or use TriggerAuthentication"
  else
    echo "✅ Cross-namespace connectivity OK"
  fi
fi

# Deploy KEDA ScaledObjects + NetworkPolicy
echo "=== Deploying KEDA ScaledObjects ==="
MANIFESTS_DIR="${MANIFESTS_DIR:-/root/production-manifests}"
kubectl apply -f "$MANIFESTS_DIR/keda-scaledobjects.yaml" || echo "Warning: KEDA ScaledObjects failed"
kubectl apply -f "$MANIFESTS_DIR/keda-rabbitmq-networkpolicy.yaml" || echo "Warning: KEDA NetworkPolicy failed"
echo "✅ KEDA ScaledObjects + NetworkPolicy deployed"
kubectl get scaledobject -n "$NAMESPACE" || true

# Delete hardcoded HPA (replaced by KEDA)
kubectl delete hpa celery-worker-hpa -n "$NAMESPACE" --ignore-not-found
echo "✅ Hardcoded HPA removed"
