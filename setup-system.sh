#!/bin/bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}   Meeting Automation - Local Development Setup     ${NC}"
echo -e "${BLUE}====================================================${NC}"

# 0. Check for docker-compose command
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo -e "${RED}Error: docker-compose not found.${NC}"
    exit 1
fi

# 1. Environment Configuration
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env from .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}Please review .env settings.${NC}"
fi

# 2. Wait for Database to be ready
echo -e "${YELLOW}Waiting for PostgreSQL to be healthy...${NC}"
until $DOCKER_COMPOSE exec -T postgres pg_isready -U meeting_user -d meeting_db > /dev/null 2>&1; do
  echo -e "${BLUE}Postgres is starting up...${NC}"
  sleep 3
done
echo -e "${GREEN}PostgreSQL is ready!${NC}"

# 3. Run Database Migrations
echo -e "${YELLOW}Checking database migration status...${NC}"
$DOCKER_COMPOSE exec -T backend alembic upgrade head
echo -e "${GREEN}Database schema is up to date.${NC}"

# 4. Seed Test Users
echo -e "${YELLOW}Seeding enterprise test users...${NC}"
$DOCKER_COMPOSE exec -T backend python scripts/seed_users.py
echo -e "${GREEN}Users seeded successfully.${NC}"

# 5. Initialize MinIO / S3 Buckets
echo -e "${YELLOW}Creating S3 buckets...${NC}"
$DOCKER_COMPOSE exec -T minio mc alias set myminio http://localhost:9000 minio_user minio_password
$DOCKER_COMPOSE exec -T minio mc mb myminio/recordings --ignore-existing
$DOCKER_COMPOSE exec -T minio mc mb myminio/meeting-recordings-staging --ignore-existing
echo -e "${GREEN}S3 infrastructure ready.${NC}"

# 6. LiveKit on Host (UDP direct access)
echo -e "${YELLOW}Ensuring LiveKit runs on host (UDP direct access)...${NC}"
if curl -sf http://localhost:7880 > /dev/null 2>&1; then
    echo -e "${GREEN}LiveKit already running on host (port 7880).${NC}"
else
    echo -e "${YELLOW}Starting LiveKit on host via Docker Compose...${NC}"
    $DOCKER_COMPOSE up -d livekit-server livekit-redis
    sleep 5
    if curl -sf http://localhost:7880 > /dev/null 2>&1; then
        echo -e "${GREEN}LiveKit started successfully on host.${NC}"
    else
        echo -e "${RED}Warning: LiveKit may not be running. Check with: docker logs livekit-server${NC}"
    fi
fi

# 6.1 Verify LiveKit webhook reaches backend
echo -e "${YELLOW}Verifying LiveKit webhook URL...${NC}"
WEBHOOK_RESP=$(curl -sf -o /dev/null -w '%{http_code}' http://172.18.0.1:8000/api/v1/livekit/webhooks 2>/dev/null || echo "000")
if [ "$WEBHOOK_RESP" = "405" ] || [ "$WEBHOOK_RESP" = "422" ]; then
    echo -e "${GREEN}LiveKit webhook endpoint reachable (HTTP ${WEBHOOK_RESP} = OK for GET on POST-only endpoint).${NC}"
else
    echo -e "${RED}Warning: LiveKit webhook endpoint not reachable on port 8000 (HTTP ${WEBHOOK_RESP}). Pipeline may not work.${NC}"
fi

# 7. n8n Workflow Setup
echo -e "${YELLOW}==================================================${NC}"
echo -e "${RED}IMPORTANT: n8n Workflow Manual Setup Required!${NC}"
echo -e "${YELLOW}==================================================${NC}"
echo -e "1. Open n8n UI at: ${BLUE}http://localhost:5678${NC}"
echo -e "2. Complete initial owner account setup"
echo -e "3. Import workflows from: ${BLUE}./n8n/workflows/*.json${NC}"
echo -e "4. Configure SMTP credentials in each workflow"
echo -e "5. ${RED}ACTIVATE${NC} each workflow (Toggle → Green)"
echo -e "${YELLOW}==================================================${NC}"
echo -e ""

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}   SETUP COMPLETED SUCCESSFULLY!                   ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "Frontend:    http://localhost:3000"
echo -e "Backend:     http://localhost:8000"
echo -e "LiveKit:     ws://localhost:7880 (host networking)"
echo -e "n8n:         http://localhost:5678"
echo -e "OnlyOffice:  http://localhost:8081"
echo -e ""
echo -e "Login: dg@meeting.tn / Password123!"
