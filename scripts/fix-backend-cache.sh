#!/bin/bash
# Robust script to fix backend dependency issues by bypassing cache

echo "🧹 Cleaning up old containers and forcing a clean build..."

# Ensure we are in the root directory
cd "$(dirname "$0")/.."

# Force stop and remove containers/orphans
docker-compose down --remove-orphans

# Build backend without cache to ensure requirements.txt is fresh
docker-compose build --no-cache backend

# Start the system back up
docker-compose up -d

echo "✅ Backend rebuilt without cache and restarted."
echo "🔍 Verifying installed packages in the running container..."
sleep 5
docker-compose exec -T backend pip show email-validator || echo "❌ email-validator STILL NOT FOUND"

echo "📋 Checking backend logs..."
docker-compose logs --tail=20 backend
