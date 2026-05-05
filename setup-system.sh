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

# 3. Run Database Migrations (Alembic)
echo -e "${YELLOW}Checking database state for Alembic migrations...${NC}"
TABLE_EXISTS=$($DOCKER_COMPOSE exec -T postgres psql -U meeting_user -d meeting_db -tAc "SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename  = 'users');")

if [ "$TABLE_EXISTS" = "t" ]; then
    echo -e "${BLUE}Tables already auto-created by backend. Syncing Alembic state...${NC}"
    $DOCKER_COMPOSE exec -T backend alembic stamp head
else
    echo -e "${YELLOW}Running Alembic migrations from scratch...${NC}"
    $DOCKER_COMPOSE exec -T backend alembic upgrade head
fi
echo -e "${GREEN}Database schema is up to date.${NC}"

# 4. Create n8n Helper Table (Not in standard migrations)
echo -e "${YELLOW}Initializing n8n auxiliary table (n8n_meetings)...${NC}"
$DOCKER_COMPOSE exec -T postgres psql -U meeting_user -d meeting_db -c "
CREATE TABLE IF NOT EXISTS n8n_meetings (
    id SERIAL PRIMARY KEY,
    meeting_id VARCHAR(255) NOT NULL,
    title TEXT,
    start_time VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);"
echo -e "${GREEN}n8n table initialized.${NC}"

# 5. Seed Test Users
echo -e "${YELLOW}Seeding enterprise test users...${NC}"
$DOCKER_COMPOSE exec -T backend python scripts/seed_users.py
echo -e "${GREEN}Users seeded successfully.${NC}"

# 6. Initialize MinIO / S3 Buckets
echo -e "${YELLOW}Waiting for MinIO API...${NC}"
sleep 5
echo -e "${YELLOW}Creating S3 bucket 'meeting-recordings'...${NC}"
# Use the local script content to ensure it runs inside the container
$DOCKER_COMPOSE exec -T backend python - < scripts/create_s3_bucket.py
echo -e "${GREEN}S3 infrastructure ready.${NC}"

# 7. Import n8n Workflows
echo -e "${YELLOW}Importing n8n workflows...${NC}"
WORKFLOWS_DIR="./n8n/workflows"
if [ -d "$WORKFLOWS_DIR" ]; then
    IMPORTED=0
    for workflow_file in "$WORKFLOWS_DIR"/*.json; do
        if [ -f "$workflow_file" ]; then
            WORKFLOW_NAME=$(basename "$workflow_file" .json)
            echo -e "${BLUE}Importing workflow: $WORKFLOW_NAME...${NC}"
            $DOCKER_COMPOSE exec -T n8n n8n import:workflow --input="$workflow_file" 2>/dev/null && IMPORTED=$((IMPORTED + 1)) || echo -e "${YELLOW}Warning: Failed to import $WORKFLOW_NAME (may already exist)${NC}"
        fi
    done
    echo -e "${GREEN}n8n workflows imported: $IMPORTED/${IMPORTED}${NC}"
else
    echo -e "${YELLOW}n8n workflows directory not found, skipping...${NC}"
fi

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}   SETUP COMPLETED SUCCESSFULLY!                   ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "You can now login at http://localhost:3000"
echo -e "Don't forget to activate n8n workflows at http://localhost:5678"
