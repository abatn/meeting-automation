#!/bin/bash
# 07-smoke-tests.sh — Ensure E2E Test User + Health Check
# Env: KUBECONFIG, E2E_TEST_USER_EMAIL, E2E_TEST_USER_PASSWORD
set -e

export KUBECONFIG="${KUBECONFIG:-$(pwd)/kubeconfig-staging}"
STAGING_URL="${STAGING_URL:-https://staging.meeting-automation.com}"

echo "=== Ensure E2E Test User ==="
for i in $(seq 1 30); do
  if curl -s -f "$STAGING_URL/health" > /dev/null; then
    echo "Backend is ready"
    break
  fi
  echo "Waiting for backend... ($i/30)"
  sleep 2
done

REGISTER_PAYLOAD=$(jq -n \
  --arg email "$E2E_TEST_USER_EMAIL" \
  --arg password "$E2E_TEST_USER_PASSWORD" \
  --arg name "E2E Tester" \
  '{
    email: $email,
    password: $password,
    full_name: $name,
    company_name: "E2E Tests"
  }')
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$STAGING_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "$REGISTER_PAYLOAD")
if [ "$RESPONSE" = "201" ] || [ "$RESPONSE" = "200" ]; then
  echo "✅ Test user created or already exists"
else
  echo "⚠️ Could not create test user (HTTP $RESPONSE)"
fi

echo "=== Health Check ==="
echo "Waiting for $STAGING_URL/health..."
for i in $(seq 1 60); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$STAGING_URL/health" 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo "✅ Staging is healthy"
    break
  fi
  echo "Health check returned $STATUS, waiting... (attempt $i)"
  sleep 5
done
curl -f "$STAGING_URL/health" || (echo "❌ Staging health check failed" && exit 1)
