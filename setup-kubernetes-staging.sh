#!/bin/bash
set -euo pipefail

# Colors for professional output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

NAMESPACE="meeting-automation-staging"
POSTGRES_POD="postgres-staging-0"
DB_USER="meeting_user"
DB_NAME="meeting_db_staging"
INFRA_DIR="./infrastructure/kubernetes/staging"

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}   Meeting Automation - Staging k3s Initialization  ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}   Namespace : ${NAMESPACE}${NC}"
echo -e "${BLUE}   Database  : ${DB_NAME}${NC}"
echo -e "${BLUE}====================================================${NC}"

# 0. Prüfe kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed or not in PATH.${NC}"
    exit 1
fi

# Setze KUBECONFIG falls Datei vorhanden
if [ -f "./kubeconfig-staging.txt" ]; then
    export KUBECONFIG="$(pwd)/kubeconfig-staging.txt"
    echo -e "${GREEN}Using kubeconfig: ./kubeconfig-staging.txt${NC}"
elif [ -f "$HOME/.kube/config-staging" ]; then
    export KUBECONFIG="$HOME/.kube/config-staging"
    echo -e "${GREEN}Using kubeconfig: ~/.kube/config-staging${NC}"
fi

# Prüfe ob staging-cluster Context existiert
if ! kubectl config get-contexts 2>/dev/null | grep -q "staging-cluster"; then
    echo -e "${RED}Error: Context 'staging-cluster' not found in kubeconfig.${NC}"
    kubectl config get-contexts 2>/dev/null || true
    exit 1
fi
kubectl config use-context staging-cluster > /dev/null
echo -e "${GREEN}Context: staging-cluster${NC}"

# 1. Namespace sicherstellen
echo -e "${YELLOW}[1/8] Prüfe Namespace '${NAMESPACE}'...${NC}"
if kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    echo -e "${GREEN}Namespace existiert bereits.${NC}"
else
    kubectl apply -f "${INFRA_DIR}/namespace.yaml"
    echo -e "${GREEN}Namespace erstellt.${NC}"
fi

# 2. Deploy all manifests
echo -e "${YELLOW}[2/8] Deploye K8s-Manifeste...${NC}"
for f in postgres-secrets redis-secrets rabbitmq-secrets minio-secrets n8n-secrets backend-secrets livekit-secrets; do
    kubectl apply -f "${INFRA_DIR}/${f}.yaml" 2>/dev/null || true
done
kubectl apply -f "${INFRA_DIR}/backend-config.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/livekit-configmap.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/livekit-egress-configmap.yaml" 2>/dev/null || true

# Frontend Nginx ConfigMap (FQDNs für K8s DNS)
sed 's/resolver 127.0.0.11 10.96.0.10 valid=10s;/resolver kube-dns.kube-system.svc.cluster.local valid=30s;/g; s|http://backend:8000|http://backend.'${NAMESPACE}'.svc.cluster.local:8000|g; s|http://onlyoffice:80|http://onlyoffice-staging.'${NAMESPACE}'.svc.cluster.local:80|g' frontend/nginx.conf | \
    kubectl create configmap frontend-nginx-config \
    --from-file=default.conf=/dev/stdin \
    -n "${NAMESPACE}" \
    --dry-run=client -o yaml 2>/dev/null | \
    kubectl apply -f - 2>/dev/null || echo -e "${YELLOW}  Warning: Failed to create frontend-nginx-config${NC}"

kubectl apply -f "${INFRA_DIR}/postgres-statefulset.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/redis-deployment.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/rabbitmq-statefulset.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/minio-statefulset.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/backend-deployment.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/frontend-deployment.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/celery-worker-deployment.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/celery-beat-deployment.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/n8n-deployment.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/onlyoffice-deployment.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/livekit-server-deployment.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/livekit-egress-deployment.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/network-policies.yaml" 2>/dev/null || true
echo -e "${GREEN}Manifeste deployt.${NC}"

# 3. Warte auf Pods
echo -e "${YELLOW}[3/8] Warte auf Pods...${NC}"
kubectl wait --for=condition=ready pod -l app=postgres-staging -n "${NAMESPACE}" --timeout=120s 2>/dev/null || true
kubectl wait --for=condition=ready pod -l app=backend -n "${NAMESPACE}" --timeout=180s 2>/dev/null || true
echo -e "${GREEN}Pods bereit.${NC}"

# 4. Migrationen
echo -e "${YELLOW}[4/8] Alembic Migrationen...${NC}"

# Kopiere Migrationen in alle Backend-Pods
BACKEND_PODS=$(kubectl get pods -n "${NAMESPACE}" -l app=backend \
    -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
if [ -n "${BACKEND_PODS}" ]; then
    for pod_name in $BACKEND_PODS; do
        for migration_file in backend/alembic/versions/*.py; do
            filename=$(basename "$migration_file")
            if [ "$filename" != "__pycache__" ] && [ "$filename" != ".gitkeep" ] && [[ "$filename" != _* ]]; then
                kubectl cp "$migration_file" "${NAMESPACE}/${pod_name}:/app/alembic/versions/${filename}" 2>/dev/null || true
            fi
        done
    done
fi

# Prüfe verwaisten Stempel
ALEMBIC_STAMPED=$(kubectl exec -i "${POSTGRES_POD}" -n "${NAMESPACE}" -- \
    psql -U "${DB_USER}" -d "${DB_NAME}" -tAc \
    "SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'alembic_version');" 2>/dev/null || echo "f")
if [ "${ALEMBIC_STAMPED}" = "t" ]; then
    TABLE_EXISTS=$(kubectl exec -i "${POSTGRES_POD}" -n "${NAMESPACE}" -- \
        psql -U "${DB_USER}" -d "${DB_NAME}" -tAc \
        "SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'users');" 2>/dev/null || echo "f")
    if [ "${TABLE_EXISTS}" = "f" ]; then
        kubectl exec -i "${POSTGRES_POD}" -n "${NAMESPACE}" -- \
            psql -U "${DB_USER}" -d "${DB_NAME}" -c "DELETE FROM alembic_version;" > /dev/null 2>&1
    fi
fi

kubectl exec -i "deployment/backend" -n "${NAMESPACE}" -- \
    bash -c "export PYTHONPATH=/app && cd /app && alembic upgrade head" 2>/dev/null || true
echo -e "${GREEN}Migrationen aktuell.${NC}"

# 5. n8n Hilfstabelle + Users seeden
echo -e "${YELLOW}[5/8] Seed users + n8n table...${NC}"
kubectl exec -i "${POSTGRES_POD}" -n "${NAMESPACE}" -- \
    psql -U "${DB_USER}" -d "${DB_NAME}" -c "
CREATE TABLE IF NOT EXISTS n8n_meetings (
    id SERIAL PRIMARY KEY,
    meeting_id VARCHAR(255) NOT NULL,
    title TEXT,
    start_time VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);" > /dev/null 2>&1

kubectl exec -i "deployment/backend" -n "${NAMESPACE}" -- \
    bash -c "export PYTHONPATH=/app && cd /app && python scripts/seed_users.py" 2>/dev/null || true

kubectl create secret generic e2e-test-user \
    --namespace "${NAMESPACE}" \
    --from-literal=E2E_TEST_USER_EMAIL="e2e-tester@staging.meeting.tn" \
    --from-literal=E2E_TEST_USER_PASSWORD="Password123!" \
    --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1
echo -e "${GREEN}Users gesetzt.${NC}"

# 6. S3 Bucket erstellen
echo -e "${YELLOW}[6/8] Erstelle S3 Bucket...${NC}"
MINIO_ENDPOINT="http://minio-staging.${NAMESPACE}.svc.cluster.local:9000"
kubectl exec -i "deployment/backend" -n "${NAMESPACE}" -- \
    bash -c "export PYTHONPATH=/app && cd /app && python -c \"
import boto3
from botocore.config import Config
s3 = boto3.client('s3',
    endpoint_url='${MINIO_ENDPOINT}',
    aws_access_key_id='minio_user',
    aws_secret_access_key='minio_password',
    config=Config(signature_version='s3v4'),
    region_name='us-east-1')
buckets = [b['Name'] for b in s3.list_buckets()['Buckets']]
if 'meeting-recordings-staging' not in buckets:
    s3.create_bucket(Bucket='meeting-recordings-staging')
    print('Created bucket: meeting-recordings-staging')
else:
    print('Bucket already exists: meeting-recordings-staging')
\"" 2>/dev/null || true
echo -e "${GREEN}S3 Bucket bereit.${NC}"

# 7. Status anzeigen
echo -e "${YELLOW}[7/8] Pod-Status:${NC}"
kubectl get pods -n "${NAMESPACE}" -o wide
echo ""
echo -e "${YELLOW}Tabellen:${NC}"
kubectl exec -i "${POSTGRES_POD}" -n "${NAMESPACE}" -- \
    psql -U "${DB_USER}" -d "${DB_NAME}" -c \
    "SELECT COUNT(*) AS tabellen FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null || true
echo ""
echo -e "${YELLOW}Users:${NC}"
kubectl exec -i "${POSTGRES_POD}" -n "${NAMESPACE}" -- \
    psql -U "${DB_USER}" -d "${DB_NAME}" -c \
    "SELECT email, status, is_superuser FROM users ORDER BY created_at;" 2>/dev/null || true

# 8. Smoke Tests
echo -e "${YELLOW}[8/8] E2E Smoke Tests...${NC}"
kubectl port-forward svc/backend 18001:8000 -n "${NAMESPACE}" &>/dev/null &
PF_BACKEND_PID=$!
kubectl port-forward svc/frontend 13001:80 -n "${NAMESPACE}" &>/dev/null &
PF_FRONTEND_PID=$!
sleep 3

SMOKE_OK=true

HEALTH=$(curl -sf http://localhost:18001/health 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
if [ "$HEALTH" = "healthy" ]; then
    echo -e "${GREEN}  ✅ Backend healthy${NC}"
else
    echo -e "${RED}  ❌ Backend health failed (${HEALTH})${NC}"
    SMOKE_OK=false
fi

LOGIN_HEADERS=$(mktemp)
curl -sf -D "$LOGIN_HEADERS" -X POST http://localhost:18001/api/v1/auth/login \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=dg%40meeting.tn&password=Password123%21" > /dev/null 2>&1
ACCESS_TOKEN=$(grep -oP 'accessToken=\K[^;]+' "$LOGIN_HEADERS" 2>/dev/null || echo "")
rm -f "$LOGIN_HEADERS"
if [ -n "$ACCESS_TOKEN" ]; then
    echo -e "${GREEN}  ✅ Login successful${NC}"
else
    echo -e "${RED}  ❌ Login failed${NC}"
    SMOKE_OK=false
fi

if [ -n "$ACCESS_TOKEN" ]; then
    ME_INFO=$(curl -sf http://localhost:18001/api/v1/auth/me \
        -H "Cookie: accessToken=$ACCESS_TOKEN" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('email',''))" 2>/dev/null || echo "")
    if [ "$ME_INFO" = "dg@meeting.tn" ]; then
        echo -e "${GREEN}  ✅ User info correct${NC}"
    else
        echo -e "${RED}  ❌ User info failed${NC}"
        SMOKE_OK=false
    fi
fi

if [ -n "$ACCESS_TOKEN" ]; then
    MEETING_RESP=$(curl -sf -X POST http://localhost:18001/api/v1/meetings/ \
        -H "Cookie: accessToken=$ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"title":"Staging Smoke Test","start_time":"2026-06-23T10:00:00Z"}' 2>/dev/null || echo "")
    MEETING_STATUS=$(echo "$MEETING_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
    if [ "$MEETING_STATUS" = "PLANNED" ] || [ "$MEETING_STATUS" = "planned" ]; then
        echo -e "${GREEN}  ✅ Meeting created${NC}"
    else
        echo -e "${RED}  ❌ Meeting creation failed (${MEETING_RESP:0:100})${NC}"
        SMOKE_OK=false
    fi
fi

FE_CODE=$(curl -sf -o /dev/null -w '%{http_code}' http://localhost:13001/ 2>/dev/null || echo "000")
if [ "$FE_CODE" = "200" ]; then
    echo -e "${GREEN}  ✅ Frontend HTTP 200${NC}"
else
    echo -e "${RED}  ❌ Frontend HTTP ${FE_CODE}${NC}"
    SMOKE_OK=false
fi

kill $PF_BACKEND_PID $PF_FRONTEND_PID 2>/dev/null || true

echo ""
if [ "$SMOKE_OK" = true ]; then
    echo -e "${GREEN}====================================================${NC}"
    echo -e "${GREEN}   ✅ ALL SMOKE TESTS PASSED${NC}"
    echo -e "${GREEN}====================================================${NC}"
else
    echo -e "${RED}====================================================${NC}"
    echo -e "${RED}   ❌ SOME SMOKE TESTS FAILED${NC}"
    echo -e "${RED}====================================================${NC}"
fi

echo ""
echo -e "${GREEN}Nächste Schritte:${NC}"
echo -e "  kubectl get pods -n ${NAMESPACE}"
echo -e "  kubectl port-forward svc/frontend 3001:80 --address 0.0.0.0 -n ${NAMESPACE}"
echo -e "  kubectl port-forward svc/backend 8001:8000 --address 0.0.0.0 -n ${NAMESPACE}"
echo -e "  # Login: dg@meeting.tn / Password123!"
echo ""
