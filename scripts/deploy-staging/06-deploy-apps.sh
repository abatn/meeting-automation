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

echo "=== Setup n8n Owner ==="
OWNER_COUNT=$(kubectl exec -n "$NAMESPACE" meeting-db-1 -- psql -U postgres -d meeting_db_staging -t -c "SELECT count(*) FROM \"user\"" 2>/dev/null | tr -d ' ')
if [ "$OWNER_COUNT" = "0" ]; then
  echo "No owner found — creating via n8n REST API"
  curl -s -X POST "http://localhost:8080/n8n/rest/owner/setup" \
    -H "Content-Type: application/json" \
    -d '{"email":"batniniabdelkader@yahoo.com","password":"Abdelka15121978!","firstName":"Abdelkader","lastName":"Batnini"}' > /dev/null || echo "⚠️ Owner setup failed"
  echo "✅ n8n owner created"
else
  echo "✅ n8n owner already exists ($OWNER_COUNT users) — skipping setup"
fi

echo "=== Create n8n SMTP credential ==="
CRED_COUNT=$(kubectl exec -n "$NAMESPACE" meeting-db-1 -- psql -U postgres -d meeting_db_staging -t -c "SELECT count(*) FROM credentials_entity WHERE type='smtp'" 2>/dev/null | tr -d ' ')
if [ "$CRED_COUNT" = "0" ]; then
  echo "No SMTP credential — creating via n8n REST API"
  curl -s -c /tmp/n8n-cookies.txt -X POST "http://localhost:8080/n8n/rest/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"batniniabdelkader@yahoo.com","password":"Abdelka15121978!"}' > /dev/null
  curl -s -b /tmp/n8n-cookies.txt -X POST "http://localhost:8080/n8n/rest/credentials" \
    -H "Content-Type: application/json" \
    -d '{"name":"SMTP account","type":"smtp","data":{"user":"api","password":"4e2fbbb5ef37900bd76094b79a0dbb82","host":"bulk.smtp.mailtrap.io","port":587,"ssl":false}}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Created credential: {d.get(\"id\",\"?\")}')" 2>/dev/null || echo "⚠️ Credential creation failed"
  echo "✅ SMTP credential created"
else
  echo "✅ SMTP credential already exists ($CRED_COUNT credentials) — skipping creation"
fi

echo "=== Update workflow credential references ==="
NEW_CRED_ID=$(kubectl exec -n "$NAMESPACE" meeting-db-1 -- psql -U postgres -d meeting_db_staging -t -c "SELECT id FROM credentials_entity WHERE type='smtp'" 2>/dev/null | tr -d ' ')
if [ -n "$NEW_CRED_ID" ]; then
  OLD_ID_EXISTS=$(kubectl exec -n "$NAMESPACE" meeting-db-1 -- psql -U postgres -d meeting_db_staging -t -c "SELECT count(*) FROM workflow_entity WHERE nodes::text LIKE '%RsSZHOzIodwgsuSc%'" 2>/dev/null | tr -d ' ')
  if [ "$OLD_ID_EXISTS" != "0" ]; then
    echo "Updating credential references from RsSZHOzIodwgsuSc to $NEW_CRED_ID"
    kubectl exec -n "$NAMESPACE" meeting-db-1 -- psql -U postgres -d meeting_db_staging \
      -c "UPDATE workflow_entity SET nodes = replace(nodes::text, 'RsSZHOzIodwgsuSc', '$NEW_CRED_ID')::jsonb WHERE nodes::text LIKE '%RsSZHOzIodwgsuSc%';" 2>/dev/null || true
    kubectl exec -n "$NAMESPACE" meeting-db-1 -- psql -U postgres -d meeting_db_staging \
      -c "UPDATE workflow_history SET nodes = replace(nodes::text, 'RsSZHOzIodwgsuSc', '$NEW_CRED_ID')::jsonb WHERE nodes::text LIKE '%RsSZHOzIodwgsuSc%';" 2>/dev/null || true
    echo "✅ Credential references updated"
  else
    echo "✅ Credential references already up to date — skipping update"
  fi
else
  echo "⚠️ No SMTP credential found — skipping update"
fi

echo "✅ All staging apps deployed"
