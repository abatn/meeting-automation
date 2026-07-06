#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

NAMESPACE="meeting-automation-staging"
INFRA_DIR="./infrastructure/kubernetes/staging"
DB_NAME="meeting_db_staging"

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}   Meeting Automation - Staging k3s Deployment      ${NC}"
echo -e "${BLUE}====================================================${NC}"

# 0. Checks
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl not found.${NC}"
    exit 1
fi

if [ -f "./kubeconfig-staging.txt" ]; then
    export KUBECONFIG="$(pwd)/kubeconfig-staging.txt"
elif [ -f "$HOME/.kube/config-staging" ]; then
    export KUBECONFIG="$HOME/.kube/config-staging"
fi

if ! kubectl config get-contexts 2>/dev/null | grep -q "staging-cluster"; then
    echo -e "${RED}Error: Context 'staging-cluster' not found.${NC}"
    exit 1
fi
kubectl config use-context staging-cluster > /dev/null
echo -e "${GREEN}Context: staging-cluster${NC}"

# Node-Check
echo -e "${YELLOW}[0/10] Node-Status...${NC}"
kubectl get nodes -o wide 2>&1 | awk '{print $1, $2, $5}' | head -5

# 1. Namespace
echo -e "${YELLOW}[1/10] Namespace...${NC}"
kubectl apply -f "${INFRA_DIR}/namespace.yaml" 2>/dev/null || true
echo -e "${GREEN}Namespace ready.${NC}"

# 2. Secrets + ConfigMaps
echo -e "${YELLOW}[2/10] Secrets + ConfigMaps...${NC}"
for f in postgres-secrets redis-secrets rabbitmq-secrets minio-secrets n8n-secrets backend-secrets livekit-secrets; do
    kubectl apply -f "${INFRA_DIR}/${f}.yaml" 2>/dev/null || true
done
kubectl apply -f "${INFRA_DIR}/backend-config.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/livekit-configmap.yaml" 2>/dev/null || true
kubectl apply -f "${INFRA_DIR}/livekit-egress-configmap.yaml" 2>/dev/null || true

# Frontend Nginx ConfigMap
sed 's|http://backend:8000|http://backend.'${NAMESPACE}'.svc.cluster.local:8000|g; s|http://onlyoffice:80|http://onlyoffice-staging.'${NAMESPACE}'.svc.cluster.local:80|g' frontend/nginx.conf | \
    kubectl create configmap frontend-nginx-config \
    --from-file=default.conf=/dev/stdin \
    -n "${NAMESPACE}" \
    --dry-run=client -o yaml 2>/dev/null | \
    kubectl apply -f - 2>/dev/null || true
echo -e "${GREEN}Secrets + ConfigMaps deployed.${NC}"

# 3. CNPG Cluster (PostgreSQL HA)
echo -e "${YELLOW}[3/10] CNPG Cluster...${NC}"
kubectl apply -f "${INFRA_DIR}/cnpg-cluster.yaml" 2>/dev/null || true
echo -e "${GREEN}CNPG Cluster deployed.${NC}"

# 4. Deployments + StatefulSets
echo -e "${YELLOW}[4/10] Deployments + StatefulSets...${NC}"
for f in redis-deployment.yaml rabbitmq-statefulset.yaml minio-statefulset.yaml \
         backend-deployment.yaml frontend-deployment.yaml \
         celery-worker-deployment.yaml celery-beat-deployment.yaml \
         n8n-deployment.yaml onlyoffice-deployment.yaml \
         livekit-server-deployment.yaml livekit-egress-deployment.yaml \
         network-policies.yaml; do
    kubectl apply -f "${INFRA_DIR}/${f}" 2>/dev/null || true
done
echo -e "${GREEN}Deployments deployed.${NC}"

# 5. Docker Images importieren
echo -e "${YELLOW}[5/10] Docker Images importieren...${NC}"
BACKEND_IMG=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep meeting-automation-backend | head -1)
FRONTEND_IMG=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep meeting-automation-frontend | head -1)

if [ -n "$BACKEND_IMG" ]; then
    echo -e "  Importing backend: ${BACKEND_IMG}"
    docker save "$BACKEND_IMG" | sudo /usr/local/bin/k3s ctr -n k8s.io images import - 2>&1 | tail -1
    echo -e "${GREEN}  Backend image imported.${NC}"
else
    echo -e "${RED}  WARNING: Backend image not found in Docker. Build first: cd backend && docker build -t meeting-automation-backend:latest .${NC}"
fi

if [ -n "$FRONTEND_IMG" ]; then
    echo -e "  Importing frontend: ${FRONTEND_IMG}"
    docker save "$FRONTEND_IMG" | sudo /usr/local/bin/k3s ctr -n k8s.io images import - 2>&1 | tail -1
    echo -e "${GREEN}  Frontend image imported.${NC}"
else
    echo -e "${RED}  WARNING: Frontend image not found in Docker. Build first: cd frontend && docker build -t meeting-automation-frontend:latest .${NC}"
fi

# 6. Warte auf CNPG + Pods
echo -e "${YELLOW}[6/10] Warte auf CNPG + Pods...${NC}"
echo -e "  Warte auf CNPG meeting-db..."
kubectl wait --for=condition=Ready pod -l cnpg.io/cluster=meeting-db -n "${NAMESPACE}" --timeout=300s 2>/dev/null || true

echo -e "  Warte auf Redis..."
kubectl wait --for=condition=ready pod -l app=redis-staging -n "${NAMESPACE}" --timeout=60s 2>/dev/null || true

echo -e "  Warte auf RabbitMQ..."
kubectl wait --for=condition=ready pod -l app=rabbitmq-staging -n "${NAMESPACE}" --timeout=120s 2>/dev/null || true

echo -e "  Warte auf Backend..."
kubectl wait --for=condition=ready pod -l app=backend -n "${NAMESPACE}" --timeout=180s 2>/dev/null || true
echo -e "${GREEN}Pods bereit.${NC}"

# 7. DB Migration
echo -e "${YELLOW}[7/10] Alembic Migrationen...${NC}"
kubectl exec -i "deployment/backend" -n "${NAMESPACE}" -- \
    bash -c "export PYTHONPATH=/app && cd /app && alembic upgrade head" 2>/dev/null || true
echo -e "${GREEN}Migrationen aktuell.${NC}"

# 8. Users seeden + S3 Buckets
echo -e "${YELLOW}[8/10] Users seeden + S3 Buckets...${NC}"
kubectl exec -i "deployment/backend" -n "${NAMESPACE}" -- \
    bash -c "export PYTHONPATH=/app && cd /app && python scripts/seed_users.py" 2>/dev/null || true

kubectl create secret generic e2e-test-user \
    --namespace "${NAMESPACE}" \
    --from-literal=E2E_TEST_USER_EMAIL="e2e-tester@staging.meeting.tn" \
    --from-literal=E2E_TEST_USER_PASSWORD="Password123!" \
    --dry-run=client -o yaml | kubectl apply -f - 2>/dev/null || true

# S3 Buckets
kubectl exec -i "deployment/backend" -n "${NAMESPACE}" -- \
    bash -c "export PYTHONPATH=/app && cd /app && python -c \"
import boto3
from botocore.config import Config
s3 = boto3.client('s3',
    endpoint_url='http://minio-staging.${NAMESPACE}.svc.cluster.local:9000',
    aws_access_key_id='minio_user',
    aws_secret_access_key='minio_password',
    config=Config(signature_version='s3v4'),
    region_name='us-east-1')
for bucket in ['meeting-recordings-staging', 'recordings', 'velero-backups']:
    if bucket not in [b['Name'] for b in s3.list_buckets()['Buckets']]:
        s3.create_bucket(Bucket=bucket)
        print(f'Created: {bucket}')
    else:
        print(f'Exists: {bucket}')
\"" 2>/dev/null || true
echo -e "${GREEN}Users + S3 ready.${NC}"

# 9. Backup-Systeme konfigurieren
echo -e "${YELLOW}[9/12] Backup-Systeme...${NC}"

# Velero Backup Bucket
kubectl exec -i "deployment/backend" -n "${NAMESPACE}" -- \
    bash -c "export PYTHONPATH=/app && cd /app && python -c \"
import boto3
from botocore.config import Config
s3 = boto3.client('s3',
    endpoint_url='http://minio-staging.${NAMESPACE}.svc.cluster.local:9000',
    aws_access_key_id='minio_user',
    aws_secret_access_key='minio_password',
    config=Config(signature_version='s3v4'),
    region_name='us-east-1')
for bucket in ['meeting-recordings-staging', 'recordings', 'velero-backups']:
    if bucket not in [b['Name'] for b in s3.list_buckets()['Buckets']]:
        s3.create_bucket(Bucket=bucket)
        print(f'Created: {bucket}')
    else:
        print(f'Exists: {bucket}')
\"" 2>/dev/null || true

# Velero Secret
kubectl create secret generic velero-s3-credentials \
    --namespace velero \
    --from-literal=cloud=minio_user:minio_password \
    --dry-run=client -o yaml 2>/dev/null | kubectl apply -f - 2>/dev/null || true

# CNPG Backup CRD (initial)
cat <<'BACKUPEOF' | kubectl apply -f - 2>/dev/null || true
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: meeting-db-initial-backup
  namespace: ${NAMESPACE}
spec:
  cluster:
    name: meeting-db
  method: barmanObjectStore
BACKUPEOF

# CNPG ScheduledBackup (taeglich 2:00 AM, 30d Retention)
cat <<'SCHEDULEDEOF' | kubectl apply -f - 2>/dev/null || true
apiVersion: postgresql.cnpg.io/v1
kind: ScheduledBackup
metadata:
  name: meeting-db-daily-backup
  namespace: ${NAMESPACE}
spec:
  schedule: "0 2 * * *"
  backupOwnerReference: self
  cluster:
    name: meeting-db
  method: barmanObjectStore
SCHEDULEDEOF

echo -e "${GREEN}Backup-Systeme konfiguriert.${NC}"

# 10. Pod-Status + Login-Test
echo -e "${YELLOW}[10/12] Pod-Status...${NC}"
kubectl get pods -n "${NAMESPACE}" --no-headers 2>/dev/null | awk '{printf "  %-55s %s\n", $1, $3}'

echo ""
echo -e "${YELLOW}Login Test...${NC}"
LOGIN_RESP=$(curl -sk https://staging.meeting-automation.com/api/v1/auth/login \
    -X POST -d "username=admin@meeting.tn&password=Password123!" 2>/dev/null || echo "")
if echo "$LOGIN_RESP" | grep -q "access_token"; then
    echo -e "${GREEN}  ✅ admin@meeting.tn Login OK${NC}"
else
    echo -e "${RED}  ❌ admin@meeting.tn Login fehlgeschlagen${NC}"
fi

LOGIN_RESP=$(curl -sk https://staging.meeting-automation.com/api/v1/auth/login \
    -X POST -d "username=dg@meeting.tn&password=Password123!" 2>/dev/null || echo "")
if echo "$LOGIN_RESP" | grep -q "access_token"; then
    echo -e "${GREEN}  ✅ dg@meeting.tn Login OK${NC}"
else
    echo -e "${RED}  ❌ dg@meeting.tn Login fehlgeschlagen${NC}"
fi

# 10. Smoke Tests
echo -e "${YELLOW}[11/12] Smoke Tests...${NC}"
kubectl port-forward svc/backend 18001:8000 -n "${NAMESPACE}" &>/dev/null &
PF_BACKEND_PID=$!
sleep 3

HEALTH=$(curl -sf http://localhost:18001/health 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
if [ "$HEALTH" = "healthy" ]; then
    echo -e "${GREEN}  ✅ Backend healthy${NC}"
else
    echo -e "${RED}  ❌ Backend health failed${NC}"
fi

FE_CODE=$(curl -sf -o /dev/null -w '%{http_code}' http://localhost:13001/ 2>/dev/null || echo "000")
if [ "$FE_CODE" = "200" ]; then
    echo -e "${GREEN}  ✅ Frontend HTTP 200${NC}"
else
    echo -e "${RED}  ❌ Frontend HTTP ${FE_CODE}${NC}"
fi

EXTERNAL=$(curl -sf -o /dev/null -w '%{http_code}' https://staging.meeting-automation.com 2>/dev/null || echo "000")
if [ "$EXTERNAL" = "200" ]; then
    echo -e "${GREEN}  ✅ staging.meeting-automation.com 200${NC}"
else
    echo -e "${RED}  ❌ staging.meeting-automation.com ${EXTERNAL}${NC}"
fi

kill $PF_BACKEND_PID 2>/dev/null || true

# 12. Backup-Status
echo -e "${YELLOW}[12/12] Backup-Status...${NC}"
CNPG_ARCHIVING=$(kubectl get clusters.postgresql.cnpg.io meeting-db -n "${NAMESPACE}" -o jsonpath='{.status.conditions[?(@.type=="ContinuousArchiving")].status}' 2>/dev/null || echo "unknown")
echo -e "  CNPG ContinuousArchiving: ${CNPG_ARCHIVING}"

BACKUPS=$(kubectl get backups.postgresql.cnpg.io -n "${NAMESPACE}" --no-headers 2>/dev/null | wc -l)
echo -e "  CNPG Backups: ${BACKUPS} Backups"

SCHEDULES=$(kubectl get scheduledbackups.postgresql.cnpg.io -n "${NAMESPACE}" --no-headers 2>/dev/null | wc -l)
echo -e "  CNPG ScheduledBackups: ${SCHEDULES} Schedules"

VELERO_BSL=$(kubectl get backupstoragelocations.velero.io -n velero --no-headers 2>/dev/null | awk '{print $2}')
echo -e "  Velero BSL: ${VELERO_BSL}"

echo ""

echo ""
echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}   DEPLOYMENT COMPLETED                           ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "  Frontend:    https://staging.meeting-automation.com"
echo -e "  Backend:     https://staging.meeting-automation.com/api/v1/..."
echo -e "  n8n:         kubectl port-forward svc/n8n-staging 5678:5678 -n ${NAMESPACE}"
echo -e "  LiveKit:     ws://staging.meeting-automation.com"
echo -e ""
echo -e "  Admin Login: admin@meeting.tn / Password123!"
echo -e "  DG Login:    dg@meeting.tn / Password123!"
echo -e ""
echo -e "  DB: CNPG meeting-db-rw (HA, 1 Instance)"
echo -e "  Note: Production braucht 2 Nodes fuer CNPG HA"
echo -e ""
