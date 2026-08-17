#!/bin/bash
# deploy-all.sh — Master deploy script for production
# Orchestrates all deploy scripts in correct order
#
# Required env vars:
#   TAG              — Docker image tag (e.g., "latest" or "91e8d540")
#   BACKEND_IMAGE    — Full backend image (e.g., "docker.io/batnini/meeting-automation-backend:latest")
#   FRONTEND_IMAGE   — Full frontend image (e.g., "docker.io/batnini/meeting-automation-frontend:latest")
#
# Optional env vars:
#   NAMESPACE        — Kubernetes namespace (default: meeting-automation)
#   MANIFESTS_DIR    — Path to manifests (default: /root/production-manifests)
#   DOCKERHUB_TOKEN  — Docker Hub token for image pull
#   DOCKERHUB_USERNAME — Docker Hub username (default: batnini)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAMESPACE="${NAMESPACE:-meeting-automation}"
MANIFESTS_DIR="${MANIFESTS_DIR:-/root/production-manifests}"
export NAMESPACE MANIFESTS_DIR

echo "============================================="
echo "=== PRODUCTION DEPLOY (tag: ${TAG}) ==="
echo "============================================="
echo "Backend:  ${BACKEND_IMAGE}"
echo "Frontend: ${FRONTEND_IMAGE}"
echo "Namespace: ${NAMESPACE}"
echo "Manifests: ${MANIFESTS_DIR}"
echo ""

# Step 1: Pull images
echo ">>> Step 1/7: Pull images"
bash "$SCRIPT_DIR/01-pull-images.sh"
echo ""

# Step 2: Apply manifests
echo ">>> Step 2/7: Apply manifests"
bash "$SCRIPT_DIR/02-apply-manifests.sh"
echo ""

# Step 2b: Restart StatefulSets (probes may have changed)
echo ">>> Step 2b: Restart StatefulSets (RabbitMQ, MinIO, Postgres)"
for STS in rabbitmq minio meeting-db; do
  if kubectl get statefulset "$STS" -n "$NAMESPACE" &>/dev/null; then
    echo "  Restarting $STS..."
    kubectl rollout restart statefulset/"$STS" -n "$NAMESPACE"
  fi
done
echo "Waiting 60s for StatefulSet rollouts..."
sleep 60
for STS in rabbitmq minio meeting-db; do
  if kubectl get statefulset "$STS" -n "$NAMESPACE" &>/dev/null; then
    kubectl rollout status statefulset/"$STS" -n "$NAMESPACE" --timeout=120s || echo "⚠️ $STS rollout timed out"
  fi
done
echo "✅ StatefulSet rollouts complete"
echo ""

# Step 3: Deploy LiveKit
echo ">>> Step 3/7: Deploy LiveKit"
bash "$SCRIPT_DIR/03-deploy-livekit.sh"
echo ""

# Step 4: Velero scope check
echo ">>> Step 4/7: Velero scope check"
bash "$SCRIPT_DIR/04-velero-scope-check.sh"
echo ""

# Step 5: Install infra (Longhorn + KEDA)
echo ">>> Step 5/7: Install infrastructure"
bash "$SCRIPT_DIR/05-install-infra.sh"
echo ""

# Step 6: Deploy system (CronJobs + k3s config)
echo ">>> Step 6/7: Deploy system"
bash "$SCRIPT_DIR/06-deploy-system.sh"
echo ""

# Step 7: Deploy apps
echo ">>> Step 7/7: Deploy application images"
bash "$SCRIPT_DIR/07-deploy-apps.sh"
echo ""

# Step 8: Setup n8n (optional, can fail)
echo ">>> Step 8/8: Setup n8n"
bash "$SCRIPT_DIR/08-setup-n8n.sh" || echo "⚠️ n8n setup had warnings (non-critical)"
echo ""

# Step 9: Smoke tests
echo ">>> Step 9/9: Smoke tests"
bash "$SCRIPT_DIR/09-smoke-tests.sh" || echo "⚠️ Smoke tests had warnings (non-critical)"
echo ""

# Handle k3s restart if needed
if [ "$RESTART_K3S" = "true" ]; then
  echo "=== Restarting k3s for kubelet-arg changes ==="
  systemctl restart k3s
  echo "Waiting 30s for k3s to restart..."
  sleep 30
  for i in $(seq 1 10); do
    STATUS=$(kubectl get nodes -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")
    if [ "$STATUS" = "True" ]; then
      echo "✅ Node is Ready after k3s restart"
      break
    fi
    echo "Waiting for node to be Ready... ($i/10)"
    sleep 5
  done
fi

echo "============================================="
echo "=== DEPLOYMENT COMPLETE ==="
echo "============================================="
kubectl get pods -n "$NAMESPACE"
