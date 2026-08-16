#!/bin/bash
# 06-deploy-apps.sh — Deploy Backend + Frontend + Celery + n8n Workflows
# Env: KUBECONFIG, IMAGE_NAME, FRONTEND_IMAGE, TAG
set -e

NAMESPACE="${NAMESPACE:-meeting-automation-staging}"
export KUBECONFIG="${KUBECONFIG:-$(pwd)/kubeconfig-staging}"

echo "=== Deploy Backend ==="
kubectl set image deployment/backend \
  backend="${IMAGE_NAME}:${TAG}" \
  alembic-migrate="${IMAGE_NAME}:${TAG}" \
  -n "$NAMESPACE" --record
kubectl rollout status deployment/backend -n "$NAMESPACE" --timeout=600s

echo "=== Deploy Frontend ==="
kubectl set image deployment/frontend \
  frontend="${FRONTEND_IMAGE}:${TAG}" \
  -n "$NAMESPACE" --record
kubectl rollout status deployment/frontend -n "$NAMESPACE" --timeout=120s

echo "=== Deploy Celery Workers ==="
BACKEND_IMAGE="${IMAGE_NAME}:${TAG}"
kubectl set image deployment/celery-worker-staging celery-worker="$BACKEND_IMAGE" -n "$NAMESPACE" --record
kubectl set image deployment/celery-worker-pro-staging celery-worker="$BACKEND_IMAGE" -n "$NAMESPACE" --record
kubectl set image deployment/celery-beat-staging celery-beat="$BACKEND_IMAGE" -n "$NAMESPACE" --record

# Skip celery-worker rollout check — KEDA minReplicaCount=0 (Scale-to-Zero)
GRATUIT_MIN=$(kubectl get scaledobject celery-worker-gratuit -n "$NAMESPACE" -o jsonpath='{.spec.minReplicaCount}' 2>/dev/null || echo "0")
if [ "$GRATUIT_MIN" = "0" ]; then
  echo "⏭️ Skipping celery-worker-staging rollout (KEDA min=0, Scale-to-Zero)"
else
  kubectl rollout status deployment/celery-worker-staging -n "$NAMESPACE" --timeout=300s
fi
kubectl rollout status deployment/celery-beat-staging -n "$NAMESPACE" --timeout=120s

echo "=== Import n8n Workflows ==="
N8N_POD=$(kubectl get pods -n "$NAMESPACE" -l app=n8n-staging -o jsonpath='{.items[0].metadata.name}')
WORKFLOW_COUNT=$(kubectl exec -n "$NAMESPACE" meeting-db-1 -- psql -U postgres -d meeting_db_staging -t -c "SELECT count(*) FROM workflow_entity" 2>/dev/null | tr -d ' ')
if [ "$WORKFLOW_COUNT" = "0" ]; then
  echo "No workflows — importing..."
  kubectl exec -n "$NAMESPACE" "$N8N_POD" -- mkdir -p /home/node/.n8n/workflows
  for f in n8n/workflows/*.json; do
    name=$(basename "$f")
    cat "$f" | kubectl exec -i -n "$NAMESPACE" "$N8N_POD" -- tee "/home/node/.n8n/workflows/$name" > /dev/null
    kubectl exec -n "$NAMESPACE" "$N8N_POD" -- n8n import:workflow --input="/home/node/.n8n/workflows/$name" 2>&1 | tail -1 || true
  done
  kubectl rollout restart deployment/n8n-staging -n "$NAMESPACE"
else
  echo "✅ n8n workflows exist ($WORKFLOW_COUNT) — skipping"
fi

echo "✅ All staging apps deployed"
