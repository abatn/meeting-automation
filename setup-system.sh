#!/bin/bash
set -e

# Colors for professional output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}   Meeting Automation - System Initialization       ${NC}"
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

# 3. Check if tables exist before migration
TABLE_COUNT=$($DOCKER_COMPOSE exec -T postgres psql -U meeting_user -d meeting_db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='permissions';")
if [ "$TABLE_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}Tables already exist, stamping migration...${NC}"
    $DOCKER_COMPOSE exec -T backend alembic stamp head
else
    echo -e "${YELLOW}Running Alembic migrations...${NC}"
    $DOCKER_COMPOSE exec -T backend alembic upgrade head
fi
echo -e "${GREEN}Database schema is up to date.${NC}"

# 4. Seed Test Users
echo -e "${YELLOW}Seeding enterprise test users...${NC}"
$DOCKER_COMPOSE exec -T backend python scripts/seed_users.py
echo -e "${GREEN}Users seeded successfully.${NC}"

# 5. Initialize MinIO / S3 Buckets
echo -e "${YELLOW}Waiting for MinIO API...${NC}"
sleep 5
echo -e "${YELLOW}Creating S3 bucket 'recordings'...${NC}"
# Create bucket using MinIO client (mc) inside MinIO container
$DOCKER_COMPOSE exec -T minio mc alias set myminio http://localhost:9000 minio_user minio_password
$DOCKER_COMPOSE exec -T minio mc mb myminio/recordings --ignore-existing
echo -e "${GREEN}S3 infrastructure ready.${NC}"

# 6. n8n Workflow Setup
# NOTE: CLI import does NOT properly register webhooks!
# Workflows MUST be imported and activated via n8n UI for webhooks to work.
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
# Automated import is DISABLED - webhooks will not work via CLI
# WORKFLOWS_DIR="./n8n/workflows"
# if [ -d "$WORKFLOWS_DIR" ]; then
#     for workflow_file in "$WORKFLOWS_DIR"/*.json; do
#         $DOCKER_COMPOSE exec -T n8n n8n import:workflow --input="$workflow_file"
#     done
# fi

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}   SETUP COMPLETED SUCCESSFULLY!                   ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "You can now login at http://localhost:3000"
echo -e "Don't forget to activate n8n workflows at http://localhost:5678"
