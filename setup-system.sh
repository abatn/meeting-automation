#!/bin/bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

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

# 3. Run Database Migrations (Alembic) - Universelle Logik
echo -e "${YELLOW}Checking database migration status...${NC}"

# Prüfe, ob die Alembic-Kontrolltabelle existiert
ALEMBIC_EXISTS=$($DOCKER_COMPOSE exec -T postgres psql -U meeting_user -d meeting_db -tAc "SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'alembic_version');" 2>/dev/null)

if [ "$ALEMBIC_EXISTS" = "t" ]; then
    # Fall 1: Kontrolltabelle existiert → normales Upgrade
    echo -e "${GREEN}Alembic control table found. Running migrations...${NC}"
    $DOCKER_COMPOSE exec -T backend alembic upgrade head
else
    # Fall 2: Keine Kontrolltabelle → prüfe, ob andere Tabellen existieren
    USERS_EXISTS=$($DOCKER_COMPOSE exec -T postgres psql -U meeting_user -d meeting_db -tAc "SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'users');" 2>/dev/null)
    
    if [ "$USERS_EXISTS" = "t" ]; then
        # Fall 2a: Tabellen existieren, aber keine Kontrolltabelle → Stampen UND dann Upgraden
        echo -e "${YELLOW}Database tables found but no alembic_version. Stamping and upgrading...${NC}"
        $DOCKER_COMPOSE exec -T backend alembic stamp head
        $DOCKER_COMPOSE exec -T backend alembic upgrade head
    else
        # Fall 2b: Frische, leere Datenbank → Normales Upgrade
        echo -e "${YELLOW}Fresh database. Running migrations...${NC}"
        $DOCKER_COMPOSE exec -T backend alembic upgrade head
    fi
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
$DOCKER_COMPOSE exec -T minio mc alias set myminio http://localhost:9000 minio_user minio_password
$DOCKER_COMPOSE exec -T minio mc mb myminio/recordings --ignore-existing
echo -e "${GREEN}S3 infrastructure ready.${NC}"

# 6. n8n Workflow Setup (Manual import only - CLI breaks webhooks)
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
echo -e "You can now login at http://localhost:3000"
echo -e "Don't forget to activate n8n workflows at http://localhost:5678"
