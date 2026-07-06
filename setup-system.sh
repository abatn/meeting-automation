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

# 2. Start all services
echo -e "${YELLOW}Starting all services...${NC}"
$DOCKER_COMPOSE up -d
echo -e "${GREEN}All services started.${NC}"

# 3. Wait for Database to be ready
echo -e "${YELLOW}Waiting for PostgreSQL to be healthy...${NC}"
until $DOCKER_COMPOSE exec -T postgres pg_isready -U meeting_user -d meeting_db > /dev/null 2>&1; do
  echo -e "${BLUE}Postgres is starting up...${NC}"
  sleep 3
done
echo -e "${GREEN}PostgreSQL is ready!${NC}"

# 4. Run Database Migrations
echo -e "${YELLOW}Running Alembic migrations...${NC}"
$DOCKER_COMPOSE exec -T backend alembic upgrade head
echo -e "${GREEN}Database schema is up to date.${NC}"

# 5. Seed Test Users
echo -e "${YELLOW}Seeding enterprise test users...${NC}"
$DOCKER_COMPOSE exec -T backend python scripts/seed_users.py
echo -e "${GREEN}Users seeded successfully.${NC}"

# 6. Initialize MinIO / S3 Buckets
echo -e "${YELLOW}Creating S3 buckets...${NC}"
$DOCKER_COMPOSE exec -T minio mc alias set myminio http://localhost:9000 minio_user minio_password
$DOCKER_COMPOSE exec -T minio mc mb myminio/recordings --ignore-existing
$DOCKER_COMPOSE exec -T minio mc mb myminio/meeting-recordings-staging --ignore-existing
echo -e "${GREEN}S3 infrastructure ready.${NC}"

# 7. Verify LiveKit
echo -e "${YELLOW}Verifying LiveKit...${NC}"
if curl -sf http://localhost:7880 > /dev/null 2>&1; then
    echo -e "${GREEN}LiveKit running on host (port 7880).${NC}"
else
    echo -e "${RED}Warning: LiveKit may not be running. Check with: docker logs livekit-server${NC}"
fi

# 8. Verify LiveKit webhook reaches backend
echo -e "${YELLOW}Verifying LiveKit webhook URL...${NC}"
WEBHOOK_RESP=$(curl -sf -o /dev/null -w '%{http_code}' http://172.18.0.1:8000/api/v1/livekit/webhooks 2>/dev/null || echo "000")
if [ "$WEBHOOK_RESP" = "405" ] || [ "$WEBHOOK_RESP" = "422" ]; then
    echo -e "${GREEN}LiveKit webhook endpoint reachable (HTTP ${WEBHOOK_RESP}).${NC}"
else
    echo -e "${RED}Warning: LiveKit webhook not reachable (HTTP ${WEBHOOK_RESP}). Pipeline may not work.${NC}"
fi

# 9. Verify Backend health
echo -e "${YELLOW}Verifying Backend health...${NC}"
BACKEND_RESP=$(curl -sf http://localhost:8000/health 2>/dev/null || echo "000")
if echo "$BACKEND_RESP" | grep -q "healthy"; then
    echo -e "${GREEN}Backend healthy.${NC}"
else
    echo -e "${RED}Warning: Backend not healthy (HTTP ${BACKEND_RESP}).${NC}"
fi

# 10. n8n Workflow Setup
echo -e "${YELLOW}==================================================${NC}"
echo -e "${YELLOW}n8n: http://localhost:5678${NC}"
echo -e "${YELLOW}Import workflows from: ./n8n/workflows/*.json${NC}"
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
echo -e "MinIO:       http://localhost:9001"
echo -e "RabbitMQ:    http://localhost:15672"
echo -e "Grafana:     http://localhost:3002"
echo -e ""
echo -e "Admin Login: admin@meeting.tn / Password123!"
echo -e "DG Login:    dg@meeting.tn / Password123!"
