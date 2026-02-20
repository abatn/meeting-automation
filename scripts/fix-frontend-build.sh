#!/bin/bash

# Script to fix frontend build synchronization issues
# This script updates the package-lock.json and validates the Docker build

set -e # Exit on error

echo "🚀 Starting Frontend Build Fix..."

# 1. Navigate to frontend directory
# Ensure we are in the project root if the script is called from within 'scripts'
if [[ "$PWD" == */scripts ]]; then
    cd ..
fi

if [ ! -d "frontend" ]; then
    echo "❌ Error: 'frontend' directory not found. Please run this script from the project root."
    exit 1
fi

cd frontend

# 2. Remove old artifacts (optional but recommended for clean slate)
echo "🧹 Cleaning old node_modules..."
rm -rf node_modules package-lock.json

# 3. Synchronize package-lock.json with package.json
echo "📦 Synchronizing dependencies..."
# We use 'npm install' locally to generate a fresh, synchronized package-lock.json
# based on the current package.json which includes the new test dependencies.
npm install

# 4. Verify synchronization
echo "🔍 Verifying lockfile integrity..."
if [ -f "package-lock.json" ]; then
    echo "✅ package-lock.json successfully created and synchronized."
else
    echo "❌ Failed to create package-lock.json."
    exit 1
fi

# 5. Return to root
cd ..

# 6. Test Docker build
echo "🐳 Testing Docker build for frontend..."
docker compose build frontend

echo "✨ Success! package-lock.json is now in sync and Docker build is verified."
echo "💡 IMPORTANT: Remember to commit the updated frontend/package-lock.json to your repository."