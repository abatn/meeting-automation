#!/bin/bash
# 07-deploy-apps.sh — Deploy application images + rollout status
# Env: BACKEND_IMAGE, FRONTEND_IMAGE, NAMESPACE (default: meeting-automation)
set -e

NAMESPACE="${NAMESPACE:-meeting-automation}"
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

echo "=== Deploying with images ==="
echo "Backend:  $BACKEND_IMAGE"
echo "Frontend: $FRONTEND_IMAGE"

# Set images
kubectl set image deployment/backend \
  backend="$BACKEND_IMAGE" \
  alembic-migrate="$BACKEND_IMAGE" \
  -n "$NAMESPACE" --record
kubectl set image deployment/frontend \
  frontend="$FRONTEND_IMAGE" \
  -n "$NAMESPACE" --record
kubectl set image deployment/celery-worker \
  celery-worker="$BACKEND_IMAGE" \
  -n "$NAMESPACE" --record
kubectl set image deployment/celery-worker-pro \
  celery-worker="$BACKEND_IMAGE" \
  -n "$NAMESPACE" --record
kubectl set image deployment/celery-beat \
  celery-beat="$BACKEND_IMAGE" \
  -n "$NAMESPACE" --record

# Wait for rollout
echo "=== Waiting for rollout ==="
kubectl rollout status deployment/backend -n "$NAMESPACE" --timeout=300s || true
kubectl rollout status deployment/frontend -n "$NAMESPACE" --timeout=120s || true

# Skip celery-worker rollout check — KEDA minReplicaCount=0 (Scale-to-Zero)
GRATUIT_MIN=$(kubectl get scaledobject celery-worker-gratuit -n "$NAMESPACE" -o jsonpath='{.spec.minReplicaCount}' 2>/dev/null || echo "0")
if [ "$GRATUIT_MIN" = "0" ]; then
  echo "⏭️ Skipping celery-worker rollout (KEDA min=0, Scale-to-Zero)"
else
  kubectl rollout status deployment/celery-worker -n "$NAMESPACE" --timeout=300s || true
fi
kubectl rollout status deployment/celery-beat -n "$NAMESPACE" --timeout=120s || true

echo "✅ Application images deployed"
