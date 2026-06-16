#!/bin/bash
set -euo pipefail
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
echo_status() { echo -e "\n${BLUE}====================================================${NC}\n${BLUE}   $1${NC}\n${BLUE}====================================================${NC}\n"; }
wait_for_pods() { local l=$1 t=${2:-120} n=${3:-meeting-automation}; echo -e "${YELLOW}Waiting for $l (${t}s)...${NC}"; kubectl wait --for=condition=ready pod -l "$l" -n "$n" --timeout="${t}s" 2>/dev/null || echo -e "${RED}Warning: $l timeout${NC}"; }
echo_status "Meeting Automation — Kind Cluster Setup"
if ! command -v kubectl &>/dev/null; then echo -e "${RED}kubectl not found${NC}"; exit 1; fi
if ! command -v kind &>/dev/null; then echo -e "${RED}kind not found${NC}"; exit 1; fi
KIND_CLUSTER="${KIND_CLUSTER:-meeting-staging}"
# 1. Create Kind cluster
if ! kind get clusters 2>/dev/null | grep -q "^${KIND_CLUSTER}$"; then
    echo -e "${YELLOW}Creating Kind cluster...${NC}"
    kind create cluster --name "$KIND_CLUSTER" --wait 60s
fi
kubectl config use-context "kind-${KIND_CLUSTER}"
# 2. Namespace + Secrets (plain YAML for Kind dev)
kubectl apply -f infrastructure/kubernetes/namespace.yaml

echo -e "${YELLOW}Creating dev secrets (plain YAML)...${NC}"

cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: livekit-secrets
  namespace: meeting-automation
type: Opaque
stringData:
  LIVEKIT_API_KEY: "meeting-api-key"
  LIVEKIT_API_SECRET: "meeting-api-secret-2026"
EOF

cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secrets
  namespace: meeting-automation
type: Opaque
stringData:
  POSTGRES_USER: meeting_user
  POSTGRES_PASSWORD: meeting_password
  POSTGRES_DB: meeting_db
EOF

cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: redis-secrets
  namespace: meeting-automation
type: Opaque
stringData:
  password: redis_password
EOF

cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: rabbitmq-secrets
  namespace: meeting-automation
type: Opaque
stringData:
  RABBITMQ_DEFAULT_USER: rabbit_user
  RABBITMQ_DEFAULT_PASS: rabbit_password
  RABBITMQ_ERLANG_COOKIE: "fixed_wsl2_cookie_123"
EOF

cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: minio-secrets
  namespace: meeting-automation
type: Opaque
stringData:
  MINIO_ROOT_USER: minio_user
  MINIO_ROOT_PASSWORD: minio_password
EOF

cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: n8n-secrets
  namespace: meeting-automation
type: Opaque
stringData:
  N8N_ENCRYPTION_KEY: "n8n-encryption-key-dev"
  DB_POSTGRESDB_PASSWORD: "meeting_password"
EOF

cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: onlyoffice-secret
  namespace: meeting-automation
type: Opaque
stringData:
  JWT_SECRET: "super_secret_jwt_key_onlyoffice_2026"
EOF

cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: backend-secrets
  namespace: meeting-automation
type: Opaque
stringData:
  DATABASE_URL: "postgresql+asyncpg://meeting_user:meeting_password@postgres:5432/meeting_db"
  REDIS_URL: "redis://:redis_password@redis:6379/0"
  CELERY_BROKER_URL: "amqp://rabbit_user:rabbit_password@rabbitmq:5672/"
  SECRET_KEY: "dev-secret-key-meeting-automation-2026"
  S3_ACCESS_KEY: "minio_user"
  S3_SECRET_KEY: "minio_password"
  MISTRAL_API_KEY: "${MISTRAL_API_KEY:-}"
  GLADIA_API_KEY: "${GLADIA_API_KEY:-}"
  ONLYOFFICE_SECRET: "super_secret_jwt_key_onlyoffice_2026"
  ENCRYPTION_KEY: "6AfRJonLMRY0ZXZ7W6rmFISWHurdK_AfQ1vjK2WZ3t4="
  TOTP_ENCRYPTION_KEY: "MWF5UYgUBBiaPQB-tRw5hoCA_CGsQxDUnYVYFtiMsK4="
  INTERNAL_API_SECRET: "super-secret-automation-key-2026"
EOF
kubectl apply -f infrastructure/kubernetes/backend-config.yaml
kubectl apply -f infrastructure/kubernetes/livekit-configmap.yaml
kubectl apply -f infrastructure/kubernetes/frontend-nginx-config.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/onlyoffice-config.yaml 2>/dev/null || true
# 3. Traefik CRDs
kubectl apply -f https://raw.githubusercontent.com/traefik/traefik/v3.0/docs/content/reference/dynamic-configuration/kubernetes-crd-definition-v1.yml 2>/dev/null || true
# 4. Infrastructure
kubectl apply -f infrastructure/kubernetes/postgres-statefulset.yaml
kubectl apply -f infrastructure/kubernetes/redis-deployment.yaml
kubectl apply -f infrastructure/kubernetes/rabbitmq-statefulset.yaml
kubectl apply -f infrastructure/kubernetes/minio-statefulset.yaml
# Services
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: meeting-automation
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
  type: ClusterIP
EOF

cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: meeting-automation
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
  type: ClusterIP
EOF

cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: rabbitmq
  namespace: meeting-automation
spec:
  selector:
    app: rabbitmq
  ports:
  - name: amqp
    port: 5672
    targetPort: 5672
  - name: management
    port: 15672
    targetPort: 15672
  type: ClusterIP
EOF

cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: minio
  namespace: meeting-automation
spec:
  selector:
    app: minio
  ports:
  - port: 9000
    targetPort: 9000
  type: ClusterIP
EOF
echo -e "${YELLOW}Waiting for Postgres...${NC}"
kubectl wait --for=condition=ready pod -l app=postgres -n meeting-automation --timeout=120s
# CRITICAL: Wait and let system breathe before deploying applications
sleep 30
echo -e "${YELLOW}System stabilizing...${NC}"
# 5. n8n DB setup
sleep 5
N8N_DB_PASSWORD=$(kubectl get secret n8n-secrets -n meeting-automation -o jsonpath='{.data.DB_POSTGRESDB_PASSWORD}' 2>/dev/null | base64 --decode || echo "")
if [ -n "$N8N_DB_PASSWORD" ]; then
    kubectl exec -i postgres-0 -n meeting-automation -- psql -U postgres -c "SELECT 'CREATE DATABASE meeting_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'meeting_db')\\gexec" 2>/dev/null || true
    kubectl exec -i postgres-0 -n meeting-automation -- psql -U postgres -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'n8n') THEN CREATE ROLE n8n WITH LOGIN PASSWORD '${N8N_DB_PASSWORD}'; END IF; END \$\$;" 2>/dev/null || true
    kubectl exec -i postgres-0 -n meeting-automation -- psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE meeting_db TO n8n;" 2>/dev/null || true
fi
# 6. Application + LiveKit (deploy sequentially with delays)
echo -e "${YELLOW}Deploying applications (sequential, 8GB safe)...${NC}"

kubectl apply -f infrastructure/kubernetes/backend-deployment.yaml
kubectl patch deployment backend -n meeting-automation -p '{"spec":{"replicas":1}}' 2>/dev/null || true
sleep 10

kubectl apply -f infrastructure/kubernetes/frontend-deployment.yaml
kubectl patch deployment frontend -n meeting-automation -p '{"spec":{"replicas":1}}' 2>/dev/null || true
sleep 10

kubectl apply -f infrastructure/kubernetes/celery-worker-deployment.yaml
sleep 5

kubectl apply -f infrastructure/kubernetes/celery-beat-deployment.yaml
sleep 5

kubectl apply -f infrastructure/kubernetes/n8n-deployment.yaml
sleep 10

kubectl apply -f infrastructure/kubernetes/onlyoffice-deployment.yaml 2>/dev/null || true
sleep 10

kubectl apply -f infrastructure/kubernetes/livekit-server-deployment.yaml
kubectl apply -f infrastructure/kubernetes/livekit-server-service.yaml
sleep 5

kubectl apply -f infrastructure/kubernetes/livekit-egress-deployment.yaml
kubectl apply -f infrastructure/kubernetes/livekit-egress-service.yaml
sleep 10
# 7. Traefik
echo -e "${YELLOW}Deploying Traefik...${NC}"
kubectl apply -f infrastructure/kubernetes/traefik-rbac.yaml
sleep 3
kubectl apply -f infrastructure/kubernetes/traefik-deployment.yaml
sleep 5
kubectl apply -f infrastructure/kubernetes/traefik-middlewares.yaml 2>/dev/null || true
sleep 2
kubectl apply -f infrastructure/kubernetes/traefik-ingressroute.yaml 2>/dev/null || true
sleep 10
# 8. Load images into Kind
echo -e "${YELLOW}Loading images...${NC}"
for img in "meeting-automation-backend:latest" "meeting-automation-frontend:latest" "livekit/livekit-server:latest" "livekit/egress:latest"; do
    if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "$img"; then
        echo -e "${YELLOW}Pulling $img...${NC}"
        docker pull "$img" 2>/dev/null || true
    fi
    kind load docker-image "$img" --name "$KIND_CLUSTER" 2>/dev/null && echo -e "${GREEN}Loaded $img${NC}" || echo -e "${YELLOW}Skip $img${NC}"
done
# 9. Restart + Wait
kubectl rollout restart deployment/backend deployment/frontend deployment/celery-worker deployment/celery-beat deployment/livekit-server deployment/livekit-egress -n meeting-automation 2>/dev/null || true
wait_for_pods "app=backend" 180 || true
wait_for_pods "app=livekit-server" 60 || true
# 10. Alembic + S3
kubectl exec -i deployment/backend -n meeting-automation -- bash -c "export PYTHONPATH=/app && cd /app && alembic upgrade head" 2>/dev/null || true
kubectl exec -i statefulset/minio -n meeting-automation -- mc alias set myminio http://localhost:9000 minio_user minio_password 2>/dev/null || true
kubectl exec -i statefulset/minio -n meeting-automation -- mc mb myminio/meeting-recordings --ignore-existing 2>/dev/null || true
echo_status "KIND SETUP COMPLETE!"
kubectl get pods -n meeting-automation
echo -e "${YELLOW}Port-forward:${NC}"
echo -e "Frontend: ${BLUE}kubectl port-forward deployment/frontend 3000:80 -n meeting-automation${NC}"
echo -e "Backend:  ${BLUE}kubectl port-forward deployment/backend 8000:8000 -n meeting-automation${NC}"
echo -e "LiveKit:  ${BLUE}kubectl port-forward deployment/livekit-server 7880:7880 -n meeting-automation${NC}"
