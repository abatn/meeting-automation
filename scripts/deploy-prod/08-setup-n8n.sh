#!/bin/bash
# 08-setup-n8n.sh — Setup n8n: workflows, owner, SMTP credential
# Env: NAMESPACE (default: meeting-automation)
set -e

NAMESPACE="${NAMESPACE:-meeting-automation}"
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Import n8n workflows (idempotent: only if DB is empty)
echo "=== Import n8n workflows ==="
N8N_POD=$(kubectl get pods -n "$NAMESPACE" -l app=n8n -o jsonpath='{.items[0].metadata.name}')
WORKFLOW_COUNT=$(kubectl exec -n "$NAMESPACE" meeting-db-1 -- psql -U postgres -d meeting_db -t -c "SELECT count(*) FROM workflow_entity" 2>/dev/null | tr -d ' ')
if [ "$WORKFLOW_COUNT" = "0" ]; then
  echo "No workflows found — importing from n8n/workflows/*.json"
  kubectl exec -n "$NAMESPACE" "$N8N_POD" -- mkdir -p /home/node/.n8n/workflows
  for f in n8n/workflows/*.json; do
    name=$(basename "$f")
    echo "Importing $name..."
    cat "$f" | kubectl exec -i -n "$NAMESPACE" "$N8N_POD" -- tee "/home/node/.n8n/workflows/$name" > /dev/null
    kubectl exec -n "$NAMESPACE" "$N8N_POD" -- n8n import:workflow --input="/home/node/.n8n/workflows/$name" 2>&1 | tail -1 || true
  done
  kubectl rollout restart deployment/n8n -n "$NAMESPACE"
  echo "✅ n8n workflows imported"
else
  echo "✅ n8n workflows already exist ($WORKFLOW_COUNT workflows) — skipping import"
fi

# Setup n8n owner (idempotent: only if no owner exists)
echo "=== Setup n8n owner ==="
OWNER_COUNT=$(kubectl exec -n "$NAMESPACE" meeting-db-1 -- psql -U postgres -d meeting_db -t -c "SELECT count(*) FROM \"user\"" 2>/dev/null | tr -d ' ')
if [ "$OWNER_COUNT" = "0" ]; then
  echo "No owner found — creating via n8n REST API"
  curl -s -X POST "http://localhost:8080/n8n/rest/owner/setup" \
    -H "Content-Type: application/json" \
    -d '{"email":"batniniabdelkader@yahoo.com","password":"Abdelka15121978!","firstName":"Abdelkader","lastName":"Batnini"}' > /dev/null || echo "⚠️ Owner setup failed"
  echo "✅ n8n owner created"
else
  echo "✅ n8n owner already exists ($OWNER_COUNT users) — skipping setup"
fi

# Create n8n SMTP credential (idempotent: only if no SMTP credential exists)
echo "=== Create n8n SMTP credential ==="
CRED_COUNT=$(kubectl exec -n "$NAMESPACE" meeting-db-1 -- psql -U postgres -d meeting_db -t -c "SELECT count(*) FROM credentials_entity WHERE type='smtp'" 2>/dev/null | tr -d ' ')
if [ "$CRED_COUNT" = "0" ]; then
  echo "No SMTP credential — creating via n8n REST API"
  # Login to n8n for session cookie
  curl -s -c /tmp/n8n-cookies.txt -X POST "http://localhost:8080/n8n/rest/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"batniniabdelkader@yahoo.com","password":"Abdelka15121978!"}' > /dev/null
  # Create SMTP credential
  curl -s -b /tmp/n8n-cookies.txt -X POST "http://localhost:8080/n8n/rest/credentials" \
    -H "Content-Type: application/json" \
    -d '{"name":"SMTP account","type":"smtp","data":{"user":"api","password":"4e2fbbb5ef37900bd76094b79a0dbb82","host":"bulk.smtp.mailtrap.io","port":587,"ssl":false}}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Created credential: {d.get(\"id\",\"?\")}')" 2>/dev/null || echo "⚠️ Credential creation failed"
  echo "✅ SMTP credential created"
else
  echo "✅ SMTP credential already exists ($CRED_COUNT credentials) — skipping creation"
fi

# Update workflow credential references (idempotent: only if old ID exists)
echo "=== Update workflow credential references ==="
NEW_CRED_ID=$(kubectl exec -n "$NAMESPACE" meeting-db-1 -- psql -U postgres -d meeting_db -t -c "SELECT id FROM credentials_entity WHERE type='smtp'" 2>/dev/null | tr -d ' ')
if [ -n "$NEW_CRED_ID" ]; then
  # Check if old ID exists in workflows
  OLD_ID_EXISTS=$(kubectl exec -n "$NAMESPACE" meeting-db-1 -- psql -U postgres -d meeting_db -t -c "SELECT count(*) FROM workflow_entity WHERE nodes::text LIKE '%RsSZHOzIodwgsuSc%'" 2>/dev/null | tr -d ' ')
  if [ "$OLD_ID_EXISTS" != "0" ]; then
    echo "Updating credential references from RsSZHOzIodwgsuSc to $NEW_CRED_ID"
    kubectl exec -n "$NAMESPACE" meeting-db-1 -- psql -U postgres -d meeting_db \
      -c "UPDATE workflow_entity SET nodes = replace(nodes::text, 'RsSZHOzIodwgsuSc', '$NEW_CRED_ID')::jsonb WHERE nodes::text LIKE '%RsSZHOzIodwgsuSc%';" 2>/dev/null || true
    kubectl exec -n "$NAMESPACE" meeting-db-1 -- psql -U postgres -d meeting_db \
      -c "UPDATE workflow_history SET nodes = replace(nodes::text, 'RsSZHOzIodwgsuSc', '$NEW_CRED_ID')::jsonb WHERE nodes::text LIKE '%RsSZHOzIodwgsuSc%';" 2>/dev/null || true
    echo "✅ Credential references updated"
  else
    echo "✅ Credential references already up to date — skipping update"
  fi
else
  echo "⚠️ No SMTP credential found — skipping update"
fi
