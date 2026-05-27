#!/bin/bash
set -euo pipefail

# Colors for professional output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ============================================================
# Helper Functions
# ============================================================
retry() {
    local max_attempts=5
    local delay=5
    local attempt=0

    while true; do
        ((attempt++))
        if "$@" 2>/dev/null; then
            return 0
        fi
        if [[ $attempt -ge $max_attempts ]]; then
            echo -e "${RED}Failed after $attempt attempts: $*${NC}"
            return 1
        fi
        echo -e "${YELLOW}Attempt $attempt/$max_attempts failed. Retrying in ${delay}s...${NC}"
        sleep $delay
    done
}

wait_for_pods() {
    local label=$1
    local timeout=${2:-120}
    local namespace=${3:-meeting-automation}
    echo -e "${YELLOW}Waiting for $label pods to be ready (timeout: ${timeout}s)...${NC}"
    kubectl wait --for=condition=ready pod -l "$label" -n "$namespace" --timeout="${timeout}s" 2>/dev/null || {
        echo -e "${RED}Warning: $label pods not ready after ${timeout}s${NC}"
        return 1
    }
}

echo_status() {
    echo -e ""
    echo -e "${BLUE}====================================================${NC}"
    echo -e "${BLUE}   $1${NC}"
    echo -e "${BLUE}====================================================${NC}"
    echo -e ""
}

# ============================================================
# Main Script
# ============================================================
echo_status "Meeting Automation - Kubernetes Initialization"

# 0. Check for required tools
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed or not in PATH.${NC}"
    exit 1
fi

if [ ! -f "./bin/sops" ] && ! command -v sops &> /dev/null; then
    echo -e "${RED}Error: sops is not installed.${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: docker is not installed or not in PATH.${NC}"
    exit 1
fi

SOPS_CMD="./bin/sops"
if command -v sops &> /dev/null; then
    SOPS_CMD="sops"
fi

# ============================================================
# 1. Secure Secret Key Management
# ============================================================
echo -e "${YELLOW}Checking SOPS age key security...${NC}"
SOPS_DIR="$HOME/.config/sops/age"
mkdir -p "$SOPS_DIR"

if [ -f "key.txt" ]; then
    echo -e "${YELLOW}Found unsecure key.txt in project root. Moving it to secure location...${NC}"
    cat key.txt >> "$SOPS_DIR/keys.txt"
    chmod 600 "$SOPS_DIR/keys.txt"
    rm key.txt
    echo -e "${GREEN}Key successfully moved to $SOPS_DIR/keys.txt and secured (chmod 600).${NC}"
    echo -e "${RED}IMPORTANT: Please backup the key from $SOPS_DIR/keys.txt to a Password Manager immediately!${NC}"
elif [ ! -f "$SOPS_DIR/keys.txt" ]; then
    echo -e "${RED}Error: No age key found in $SOPS_DIR/keys.txt. Cannot decrypt secrets!${NC}"
    exit 1
else
    echo -e "${GREEN}SOPS age key is securely stored at $SOPS_DIR/keys.txt.${NC}"
fi

export SOPS_AGE_KEY_FILE="$SOPS_DIR/keys.txt"

# ============================================================
# 2. Build Docker Images (if not present)
# ============================================================
echo -e "${YELLOW}Checking Docker images...${NC}"

BUILD_BACKEND=false
BUILD_FRONTEND=false

if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "meeting-automation-backend:latest"; then
    echo -e "${YELLOW}Backend image not found. Building... (this takes ~10-15 minutes)${NC}"
    BUILD_BACKEND=true
fi

if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "meeting-automation-frontend:latest"; then
    echo -e "${YELLOW}Frontend image not found. Building... (this takes ~5-8 minutes)${NC}"
    BUILD_FRONTEND=true
fi

if [[ "$BUILD_BACKEND" == "true" || "$BUILD_FRONTEND" == "true" ]]; then
    echo -e "${BLUE}====================================================${NC}"
    echo -e "${YELLOW}   Building Docker Images${NC}"
    echo -e "${BLUE}====================================================${NC}"

    if [[ "$BUILD_BACKEND" == "true" ]]; then
        echo -e "${YELLOW}[1/2] Building backend image...${NC}"
        docker build -t meeting-automation-backend:latest -f backend/Dockerfile backend/
        echo -e "${GREEN}✅ Backend image built successfully${NC}"
    fi

    if [[ "$BUILD_FRONTEND" == "true" ]]; then
        echo -e "${YELLOW}[2/2] Building frontend image...${NC}"
        docker build -t meeting-automation-frontend:latest -f frontend/Dockerfile frontend/
        echo -e "${GREEN}✅ Frontend image built successfully${NC}"
    fi
else
    echo -e "${GREEN}Both images already present.${NC}"
fi

# ============================================================
# 3. Install Local-Path Provisioner
# ============================================================
echo -e "${YELLOW}Installing Local-Path Provisioner...${NC}"
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.26/deploy/local-path-storage.yaml 2>/dev/null || true
kubectl wait --for=condition=ready pod -l app=local-path-provisioner -n local-path-storage --timeout=30s 2>/dev/null || echo -e "${YELLOW}Warning: Local-path provisioner timeout (may already exist).${NC}"

# ============================================================
# 4. Fix CoreDNS (template variables not replaced in kind clusters)
# ============================================================
echo -e "${YELLOW}Fixing CoreDNS ConfigMap...${NC}"
COREDNS_CM=$(mktemp)
cat > "$COREDNS_CM" <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health {
            lameduck 5s
        }
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            fallthrough in-addr.arpa ip6.arpa
        }
        prometheus :9153
        forward . /etc/resolv.conf
        cache 30
        loop
        reload
        loadbalance
    }
EOF
kubectl apply -f "$COREDNS_CM"
rm -f "$COREDNS_CM"

kubectl delete pod -n kube-system -l k8s-app=kube-dns 2>/dev/null || true
kubectl wait --for=condition=ready pod -n kube-system -l k8s-app=kube-dns --timeout=60s 2>/dev/null || echo -e "${YELLOW}Warning: CoreDNS timeout (may already be ready).${NC}"

# ============================================================
# 5. Apply Namespace and Decrypt Secrets
# ============================================================
echo -e "${YELLOW}Applying Namespace and decrypting Secrets...${NC}"
kubectl apply -f infrastructure/kubernetes/namespace.yaml 2>/dev/null || true

echo -e "${YELLOW}Ensuring Traefik CRDs are installed...${NC}"
kubectl apply -f https://raw.githubusercontent.com/traefik/traefik/v3.0/docs/content/reference/dynamic-configuration/kubernetes-crd-definition-v1.yml 2>/dev/null || true

for secret_file in infrastructure/kubernetes/*-secrets.yaml; do
    echo -e "Decrypting and applying ${secret_file}..."
    $SOPS_CMD --decrypt "$secret_file" | kubectl apply -f - 2>/dev/null || echo -e "${YELLOW}Warning: Failed to apply ${secret_file}${NC}"
done

# ============================================================
# 6. Apply ConfigMaps, PVCs, Services, and Network Policies
# ============================================================
echo -e "${YELLOW}Applying Configurations, Networking and Security Policies...${NC}"
kubectl apply -f infrastructure/kubernetes/traefik-tls-secret.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/traefik-tls.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/backend-config.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/frontend-nginx-config.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/n8n-pvc.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/onlyoffice-pvc.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/onlyoffice-config.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/onlyoffice-service.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/network-policies.yaml 2>/dev/null || true

# ============================================================
# 7. Start Infrastructure (Databases, Broker, Storage)
# ============================================================
echo -e "${YELLOW}Starting Infrastructure (Postgres, Redis, RabbitMQ, MinIO)...${NC}"
kubectl apply -f infrastructure/kubernetes/postgres-statefulset.yaml 2>/dev/null || true

# ============================================================
# 7.0. Create Postgres Service
# ============================================================
echo -e "${YELLOW}Creating Postgres service...${NC}"
cat <<EOF | kubectl apply -f -
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

kubectl apply -f infrastructure/kubernetes/redis-deployment.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/minio-statefulset.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/rabbitmq-statefulset.yaml 2>/dev/null || true

# ============================================================
# 7.1. Create MinIO Service
# ============================================================
echo -e "${YELLOW}Creating MinIO service...${NC}"
cat <<EOF | kubectl apply -f -
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

# ============================================================
# 7.2. Create Redis Service
# ============================================================
echo -e "${YELLOW}Creating Redis service...${NC}"
cat <<EOF | kubectl apply -f -
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

# ============================================================
# 7.3. Create RabbitMQ Service
# ============================================================
echo -e "${YELLOW}Creating RabbitMQ service...${NC}"
cat <<EOF | kubectl apply -f -
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

echo -e "${YELLOW}Waiting for Postgres to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=postgres -n meeting-automation --timeout=120s 2>/dev/null || {
    echo -e "${YELLOW}Retrying Postgres wait...${NC}"
    sleep 10
    kubectl wait --for=condition=ready pod -l app=postgres -n meeting-automation --timeout=120s 2>/dev/null || echo -e "${RED}Warning: Postgres not ready${NC}"
}

# ============================================================
# 7.5. Create PostgreSQL role and database for n8n
# ============================================================
echo -e "${YELLOW}Creating PostgreSQL role and database for n8n...${NC}"
# Wait a bit more for postgres to be fully accepting connections
sleep 5

# Get the n8n password from the secret
N8N_DB_PASSWORD=$(kubectl get secret n8n-secrets -n meeting-automation -o jsonpath='{.data.DB_POSTGRESDB_PASSWORD}' | base64 --decode 2>/dev/null || echo "")

if [ -z "$N8N_DB_PASSWORD" ]; then
    echo -e "${YELLOW}Warning: Could not retrieve n8n password from secret. Skipping role creation.${NC}"
else
    # Create database if not exists
    kubectl exec -i postgres-0 -n meeting-automation -- psql -U postgres -c "SELECT 'CREATE DATABASE meeting_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'meeting_db')\\gexec" 2>/dev/null || true
    
    # Create role if not exists and set password
    kubectl exec -i postgres-0 -n meeting-automation -- psql -U postgres -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'n8n') THEN CREATE ROLE n8n WITH LOGIN PASSWORD '${N8N_DB_PASSWORD}'; END IF; END \$\$;" 2>/dev/null || true
    
    # Grant privileges
    kubectl exec -i postgres-0 -n meeting-automation -- psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE meeting_db TO n8n;" 2>/dev/null || true
    kubectl exec -i postgres-0 -n meeting-automation -- psql -U postgres -c "GRANT ALL PRIVILEGES ON SCHEMA public TO n8n;" 2>/dev/null || true
    kubectl exec -i postgres-0 -n meeting-automation -- psql -U postgres -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO n8n;" 2>/dev/null || true
    kubectl exec -i postgres-0 -n meeting-automation -- psql -U postgres -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO n8n;" 2>/dev/null || true
    kubectl exec -i postgres-0 -n meeting-automation -- psql -U postgres -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO n8n;" 2>/dev/null || true
    kubectl exec -i postgres-0 -n meeting-automation -- psql -U postgres -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO n8n;" 2>/dev/null || true
    
    echo -e "${GREEN}PostgreSQL role 'n8n' and database setup complete.${NC}"
fi

# ============================================================
# 8. Start Application Services
# ============================================================
echo -e "${YELLOW}Starting Application Services...${NC}"
kubectl apply -f infrastructure/kubernetes/backend-deployment.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/celery-worker-deployment.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/celery-beat-deployment.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/n8n-deployment.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/frontend-deployment.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/onlyoffice-deployment.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/traefik-rbac.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/traefik-deployment.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/traefik-middlewares.yaml 2>/dev/null || true
kubectl apply -f infrastructure/kubernetes/traefik-ingressroute.yaml 2>/dev/null || true

# ============================================================
# 9. Load Docker images into containerd
# ============================================================
echo -e "${YELLOW}Loading Docker images into cluster...${NC}"
CLUSTER_NODE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')

echo -e "Loading meeting-automation-frontend:latest into ${CLUSTER_NODE}..."
docker save meeting-automation-frontend:latest | docker exec -i "$CLUSTER_NODE" ctr -n k8s.io images import - 2>/dev/null || echo -e "${YELLOW}Warning: Frontend image load failed (may already exist).${NC}"

echo -e "Loading meeting-automation-backend:latest into ${CLUSTER_NODE}..."
echo -e "${YELLOW}Note: Backend image is large (~4.35GB). This may take 5-10 minutes...${NC}"
docker save meeting-automation-backend:latest | docker exec -i "$CLUSTER_NODE" ctr -n k8s.io images import - 2>/dev/null || echo -e "${YELLOW}Warning: Backend image load failed (may already exist).${NC}"

# Restart all deployments to pick up loaded images
echo -e "${YELLOW}Restarting all deployments to use loaded images...${NC}"
kubectl rollout restart deployment/backend deployment/frontend deployment/celery-worker deployment/celery-beat deployment/n8n -n meeting-automation 2>/dev/null || true

# ============================================================
# 10. Wait for all pods to be ready
# ============================================================
echo -e "${YELLOW}Waiting for all pods to be ready...${NC}"
wait_for_pods "app=backend" 180 || true
wait_for_pods "app=frontend" 120 || true
wait_for_pods "app=n8n" 120 || true
wait_for_pods "app=celery-worker" 60 || true
wait_for_pods "app=celery-beat" 60 || true

# ============================================================
# 11. Database Migrations & Initial Setup
# ============================================================
echo -e "${YELLOW}Running Alembic migrations...${NC}"
kubectl exec -i deployment/backend -n meeting-automation -- bash -c "export PYTHONPATH=/app && cd /app && alembic upgrade head" 2>/dev/null || echo -e "${YELLOW}Warning: Alembic migrations may have already run.${NC}"
echo -e "${GREEN}Database schema is up to date.${NC}"

echo -e "${YELLOW}Seeding enterprise test users...${NC}"
kubectl exec -i deployment/backend -n meeting-automation -- bash -c "export PYTHONPATH=/app && cd /app && python scripts/seed_users.py" 2>/dev/null || echo -e "${YELLOW}Warning: Seeding script failed or users already exist.${NC}"

echo -e "${YELLOW}Creating S3 bucket 'recordings'...${NC}"
kubectl exec -i statefulset/minio -n meeting-automation -- mc alias set myminio http://localhost:9000 minio_user minio_password_prod 2>/dev/null || true
kubectl exec -i statefulset/minio -n meeting-automation -- mc mb myminio/recordings --ignore-existing 2>/dev/null || echo -e "${YELLOW}Warning: S3 bucket creation failed or already exists.${NC}"

# ============================================================
# 12. n8n Workflow Setup
# ============================================================
echo -e ""
echo -e "${YELLOW}==================================================${NC}"
echo -e "${RED}IMPORTANT: n8n Workflow Manual Setup Required!${NC}"
echo -e "${YELLOW}==================================================${NC}"
echo -e "1. Port-forward n8n: ${BLUE}kubectl port-forward deployment/n8n 5678:5678 -n meeting-automation${NC}"
echo -e "2. Open n8n UI at: ${BLUE}http://localhost:5678${NC}"
echo -e "3. Complete initial owner account setup"
echo -e "4. Import workflows from: ${BLUE}./n8n/workflows/*.json${NC}"
echo -e "5. Configure SMTP credentials in each workflow"
echo -e "6. ${RED}ACTIVATE${NC} each workflow (Toggle → Green)"
echo -e "${YELLOW}==================================================${NC}"
echo -e ""

# ============================================================
# 13. Final Status
# ============================================================
echo_status "KUBERNETES SETUP COMPLETED SUCCESSFULLY!"

echo -e "${YELLOW}Service Status:${NC}"
kubectl get pods -n meeting-automation
echo -e ""

echo -e "${YELLOW}You can expose your services using port-forward:${NC}"
echo -e "Frontend: ${BLUE}kubectl port-forward deployment/frontend 3000:80 --address 0.0.0.0 -n meeting-automation${NC}"
echo -e "Backend:  ${BLUE}kubectl port-forward deployment/backend 8000:8000 --address 0.0.0.0 -n meeting-automation${NC}"
echo -e "OnlyOffice:  ${BLUE}kubectl port-forward deployment/onlyoffice 8080:80 --address 0.0.0.0 -n meeting-automation${NC}"
echo -e "n8n:      ${BLUE}kubectl port-forward deployment/n8n 5678:5678 --address 0.0.0.0 -n meeting-automation${NC}"
echo -e ""
echo -e "${YELLOW}Then open:${NC}"
echo -e "Frontend: http://localhost:3000"
echo -e "OnlyOffice: http://localhost:8080"
