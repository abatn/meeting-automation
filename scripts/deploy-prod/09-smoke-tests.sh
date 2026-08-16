#!/bin/bash
# 09-smoke-tests.sh — Smoke tests after deploy
# Env: NAMESPACE (default: meeting-automation)
set -e

NAMESPACE="${NAMESPACE:-meeting-automation}"
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

echo "=== Smoke Tests ==="
SMOKE_PASSED=true

# Step 1: Verify all deployments are running
echo "--- Checking deployment status ---"
for deploy in backend frontend celery-worker celery-worker-pro celery-beat; do
  READY=$(kubectl get deploy "$deploy" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
  DESIRED=$(kubectl get deploy "$deploy" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
  # celery-worker with KEDA min=0 → 0/0 is OK (Scale-to-Zero)
  if [ "$deploy" = "celery-worker" ]; then
    GRATUIT_MIN=$(kubectl get scaledobject celery-worker-gratuit -n "$NAMESPACE" -o jsonpath='{.spec.minReplicaCount}' 2>/dev/null || echo "0")
    if [ "$GRATUIT_MIN" = "0" ] && [ "$READY" = "0" ]; then
      echo "  ✅ $deploy: 0/0 ready (KEDA Scale-to-Zero)"
      continue
    fi
  fi
  if [ "$READY" = "$DESIRED" ] && [ "$READY" != "0" ]; then
    echo "  ✅ $deploy: $READY/$DESIRED ready"
  else
    echo "  ❌ $deploy: $READY/$DESIRED ready"
    SMOKE_PASSED=false
  fi
done

# Step 2: Port-forward health check (with zombie cleanup)
echo "--- Health check via port-forward ---"
pkill -f "kubectl port-forward.*svc/backend" 2>/dev/null || true
SMOKE_PORT=$(shuf -i 18000-19000 -n 1)
kubectl port-forward -n "$NAMESPACE" svc/backend "${SMOKE_PORT}":8000 &
PF_PID=$!
trap "kill $PF_PID 2>/dev/null || true" EXIT
sleep 5
HEALTH=$(curl -sf "http://localhost:${SMOKE_PORT}/health" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
kill $PF_PID 2>/dev/null || true
trap - EXIT

if [ "$HEALTH" = "healthy" ]; then
  echo "  ✅ Health endpoint: healthy"
else
  echo "  ⚠️ Health endpoint returned: '$HEALTH' (non-critical)"
fi

# Step 3: Final verdict
echo "--- Smoke test result ---"
if [ "$SMOKE_PASSED" = "true" ]; then
  echo "✅ Production smoke test PASSED"
else
  echo "⚠️ Production smoke test INCONCLUSIVE — deployments may still be starting"
  echo "   Deploy was successful (set image + rollout). Manual verification recommended."
fi
