#!/bin/bash
set -e

# Colors for professional output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}   Meeting Automation - Kubernetes Initialization   ${NC}"
echo -e "${BLUE}====================================================${NC}"

# 0. Check for required tools
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed or not in PATH.${NC}"
    exit 1
fi

if [ ! -f "./bin/sops" ] && ! command -v sops &> /dev/null; then
    echo -e "${RED}Error: sops is not installed. Please run Phase 1 Secret Management first.${NC}"
    exit 1
fi

SOPS_CMD="./bin/sops"
if command -v sops &> /dev/null; then
    SOPS_CMD="sops"
fi

# 1. Secure Secret Key Management
echo -e "${YELLOW}Checking SOPS age key security...${NC}"
SOPS_DIR="$HOME/.config/sops/age"
mkdir -p "$SOPS_DIR"

if [ -f "key.txt" ]; then
    echo -e "${YELLOW}Found unsecure key.txt in project root. Moving it to secure location...${NC}"
    # Nur überschreiben, wenn noch kein Key in keys.txt existiert oder wir es erzwingen wollen
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

# SOPS sucht standardmäßig in ~/.config/sops/age/keys.txt nach dem Key.
export SOPS_AGE_KEY_FILE="$SOPS_DIR/keys.txt"

# 2. Apply Namespace and Decrypt Secrets
echo -e "${YELLOW}Applying Namespace and decrypting Secrets...${NC}"
kubectl apply -f infrastructure/kubernetes/namespace.yaml

# Install Traefik CRDs if they don't exist
echo -e "${YELLOW}Ensuring Traefik CRDs are installed...${NC}"
kubectl apply -f https://raw.githubusercontent.com/traefik/traefik/v3.0/docs/content/reference/dynamic-configuration/kubernetes-crd-definition-v1.yml

for secret_file in infrastructure/kubernetes/*-secrets.yaml; do
    echo -e "Decrypting and applying ${secret_file}..."
    $SOPS_CMD --decrypt "$secret_file" | kubectl apply -f -
done

# 3. Apply ConfigMaps, PVCs, Services, and Network Policies
echo -e "${YELLOW}Applying Configurations, Networking and Security Policies...${NC}"
kubectl apply -f infrastructure/kubernetes/backend-config.yaml
kubectl apply -f infrastructure/kubernetes/frontend-nginx-config.yaml
kubectl apply -f infrastructure/kubernetes/n8n-pvc.yaml
kubectl apply -f infrastructure/kubernetes/services.yaml
kubectl apply -f infrastructure/kubernetes/network-policies.yaml

# 4. Start Infrastructure (Databases, Broker, Storage)
echo -e "${YELLOW}Starting Infrastructure (Postgres, Redis, RabbitMQ, MinIO)...${NC}"
kubectl apply -f infrastructure/kubernetes/postgres-statefulset.yaml
kubectl apply -f infrastructure/kubernetes/redis-deployment.yaml
kubectl apply -f infrastructure/kubernetes/minio-statefulset.yaml
kubectl apply -f infrastructure/kubernetes/rabbitmq-statefulset.yaml

echo -e "${YELLOW}Waiting for Postgres to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=postgres -n meeting-automation --timeout=120s

# 5. Start Application (Backend, Frontend, Workers, n8n)
echo -e "${YELLOW}Starting Application Services...${NC}"
kubectl apply -f infrastructure/kubernetes/backend-deployment.yaml
kubectl apply -f infrastructure/kubernetes/celery-worker-deployment.yaml
kubectl apply -f infrastructure/kubernetes/celery-beat-deployment.yaml
kubectl apply -f infrastructure/kubernetes/n8n-deployment.yaml
kubectl apply -f infrastructure/kubernetes/frontend-deployment.yaml
kubectl apply -f infrastructure/kubernetes/traefik-rbac.yaml
kubectl apply -f infrastructure/kubernetes/traefik-deployment.yaml
kubectl apply -f infrastructure/kubernetes/traefik-middlewares.yaml
kubectl apply -f infrastructure/kubernetes/traefik-ingressroute.yaml

echo -e "${YELLOW}Waiting for Backend to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=backend -n meeting-automation --timeout=120s

# 6. Database Migrations & Initial Setup
echo -e "${YELLOW}Checking database state for Alembic migrations...${NC}"
TABLE_EXISTS=$(kubectl exec -i statefulset/postgres -n meeting-automation -- psql -U meeting_user -d meeting_db -tAc "SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename  = 'users');")

if [ "$TABLE_EXISTS" = "t" ]; then
    echo -e "${BLUE}Tables already auto-created by backend. Syncing Alembic state...${NC}"
    kubectl exec -i deployment/backend -n meeting-automation -- bash -c "export PYTHONPATH=/app && cd /app && alembic stamp head"
else
    echo -e "${YELLOW}Running Alembic migrations from scratch...${NC}"
    kubectl exec -i deployment/backend -n meeting-automation -- bash -c "export PYTHONPATH=/app && cd /app && alembic upgrade head"
fi
echo -e "${GREEN}Database schema is up to date.${NC}"

echo -e "${YELLOW}Initializing n8n auxiliary table (n8n_meetings)...${NC}"
kubectl exec -i statefulset/postgres -n meeting-automation -- psql -U meeting_user -d meeting_db -c "
CREATE TABLE IF NOT EXISTS n8n_meetings (
    id SERIAL PRIMARY KEY,
    meeting_id VARCHAR(255) NOT NULL,
    title TEXT,
    start_time VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);"

echo -e "${YELLOW}Seeding enterprise test users...${NC}"
kubectl exec -i deployment/backend -n meeting-automation -- bash -c "export PYTHONPATH=/app && cd /app && python scripts/seed_users.py" || echo -e "${RED}Warning: Seeding script failed or users already exist.${NC}"

echo -e "${YELLOW}Creating S3 bucket 'meeting-recordings'...${NC}"
kubectl exec -i deployment/backend -n meeting-automation -- bash -c "export PYTHONPATH=/app && cd /app && python -" < scripts/create_s3_bucket.py || echo -e "${RED}Warning: S3 bucket creation failed or already exists.${NC}"

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}   KUBERNETES SETUP COMPLETED SUCCESSFULLY!        ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "You can expose your services using port-forward:"
echo -e "Frontend: kubectl port-forward deployment/frontend 3000:80 --address 0.0.0.0 -n meeting-automation"
echo -e "Backend:  kubectl port-forward deployment/backend 8000:8000 --address 0.0.0.0 -n meeting-automation"
echo -e "n8n:      kubectl port-forward deployment/n8n 5678:5678 --address 0.0.0.0 -n meeting-automation"
