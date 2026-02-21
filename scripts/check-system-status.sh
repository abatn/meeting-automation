#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "🔍 Checking Meeting Automation System Status..."
echo "------------------------------------------------"

# 1. Check Docker Containers
echo -n "📦 Docker Containers: "
RUNNING_CONTAINERS=$(docker ps --format '{{.Names}}' | grep "meeting-automation" | wc -l)
if [ "$RUNNING_CONTAINERS" -ge 7 ]; then
    echo -e "${GREEN}OK ($RUNNING_CONTAINERS containers running)${NC}"
else
    echo -e "${RED}WARNING (Only $RUNNING_CONTAINERS containers running)${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}" | grep "meeting-automation"
fi

# 2. Check Backend Health
echo -n "🚀 Backend API Health: "
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
if [[ $HEALTH_RESPONSE == *"healthy"* ]]; then
    echo -e "${GREEN}OK${NC}"
    echo "   Details: $HEALTH_RESPONSE"
else
    echo -e "${RED}FAILED${NC}"
fi

# 3. Check Database Connection & Migrations
echo -n "🐘 Database Connection: "
DB_CHECK=$(docker exec meeting-automation-backend-1 python3 -c "
import asyncio
from app.core.database import engine
async def check():
    try:
        async with engine.connect() as conn:
            print('Connected')
    except Exception as e:
        print(f'Error: {e}')
asyncio.run(check())
" 2>&1)
if [[ $DB_CHECK == *"Connected"* ]]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED (Check logs)${NC}"
fi

# 4. Check Frontend
echo -n "🌐 Frontend Accessibility: "
if curl -s -I http://localhost:3000 | grep -q "200 OK"; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

echo "------------------------------------------------"
echo "✅ System check complete."