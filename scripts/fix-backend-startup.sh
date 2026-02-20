#!/bin/bash
# Script to fix backend startup issue by rebuilding with missing dependency

echo "🚀 Fixing backend startup issues..."

# Ensure we are in the root directory
cd "$(dirname "$0")/.."

# Rebuild only the backend service
docker-compose build backend

# Restart the backend service
docker-compose up -d backend

echo "✅ Backend rebuilt and restarted."
echo "🔍 Checking logs..."
sleep 5
docker-compose logs --tail=20 backend
