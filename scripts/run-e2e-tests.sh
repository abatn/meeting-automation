#!/bin/bash
#
# run-e2e-tests.sh - Run E2E tests against DEV, STAGING, or PRODUCTION environments
#
set -euo pipefail

# Default values
ENVIRONMENT="dev"
BASE_URL=""
TEST_USER_EMAIL=""
TEST_USER_PASSWORD=""
MARKER="e2e"
ADDITIONAL_ARGS=""

usage() {
  cat <<EOF
Usage: $0 [OPTIONS]

Run E2E tests against a specific environment.

OPTIONS:
  --env ENV            Target environment: dev, staging, production (default: dev)
  --base-url URL       Override the base API URL (optional, usually auto-detected from env)
  --user-email EMAIL   Test user email (required for staging/production)
  --user-pass PASS     Test user password (required for staging/production)
  --marker MARKER      Pytest marker filter (default: "e2e", use "smoke" for production)
  --args "ARGS"        Additional pytest arguments (e.g., "-k test_health_check")
  -h, --help           Show this help message

EXAMPLES:
  # Run full E2E suite against local docker-compose
  $0 --env dev

  # Run E2E tests against staging
  $0 --env staging --user-email e2e-tester@staging.example.com --user-pass 'SecretPass123'

  # Run production smoke tests only
  $0 --env production --user-email admin@example.com --user-pass 'ProdPass123' --marker smoke

  # Run a specific test
  $0 --env dev --args "-k test_create_meeting_smoke -vv"

NOTE:
  For 'dev' environment, docker-compose.e2e.yml must be present and will be started automatically.
  For 'staging' and 'production', ensure you have network access and valid credentials.
EOF
  exit 1
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --user-email)
      TEST_USER_EMAIL="$2"
      shift 2
      ;;
    --user-pass)
      TEST_USER_PASSWORD="$2"
      shift 2
      ;;
    --marker)
      MARKER="$2"
      shift 2
      ;;
    --args)
      ADDITIONAL_ARGS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Error: Unknown option: $1"
      usage
      ;;
  esac
done

# Validate environment
VALID_ENVS=("dev" "staging" "production")
if [[ ! " ${VALID_ENVS[@]} " =~ " ${ENVIRONMENT} " ]]; then
  echo "Error: Invalid environment '$ENVIRONMENT'. Must be one of: ${VALID_ENVS[*]}"
  exit 1
fi

# For staging/production, require credentials
if [[ "$ENVIRONMENT" != "dev" ]]; then
  if [[ -z "$TEST_USER_EMAIL" || -z "$TEST_USER_PASSWORD" ]]; then
    echo "Error: --user-email and --user-pass are required for $ENVIRONMENT environment"
    exit 1
  fi
fi

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT"

echo "=== E2E Test Runner ==="
echo "Environment: $ENVIRONMENT"
echo "Marker: $MARKER"
echo ""

# Export environment variables for pytest
export TEST_ENV="$ENVIRONMENT"
export E2E_TEST_USER_EMAIL="${TEST_USER_EMAIL}"
export E2E_TEST_USER_PASSWORD="${TEST_USER_PASSWORD}"
if [[ -n "$BASE_URL" ]]; then
  export BASE_URL_OVERRIDE="$BASE_URL"
fi

# Set base URL if not provided
if [[ -z "$BASE_URL" ]]; then
  case "$ENVIRONMENT" in
    dev) BASE_URL="http://backend-test:8000" ;;
    staging) BASE_URL="https://staging.meeting-automate.tn" ;;
    production) BASE_URL="https://meeting-automate.tn" ;;
  esac
fi

# Handle DEV environment: start docker-compose.e2e.yml
if [[ "$ENVIRONMENT" == "dev" ]]; then
  echo "Starting local E2E test environment (docker-compose.e2e.yml)..."
  docker compose -f docker-compose.e2e.yml up -d

  echo "Waiting for backend to be healthy on http://localhost:8001..."
  for i in {1..60}; do
    if curl -s http://localhost:8001/health > /dev/null; then
      echo "Backend is healthy"
      break
    fi
    sleep 2
    printf "."
  done
  echo ""

  # Give a final health check
  if ! curl -f http://localhost:8001/health > /dev/null; then
    echo "ERROR: Backend health check failed after waiting."
    docker-compose -f docker-compose.e2e.yml logs backend
    exit 1
  fi
fi

# Build pytest command
PYTEST_CMD="pytest tests/e2e/ -v --tb=short -m \"$MARKER\" --base-url=$BASE_URL"
if [[ -n "$ADDITIONAL_ARGS" ]]; then
  PYTEST_CMD="$PYTEST_CMD $ADDITIONAL_ARGS"
fi

echo "Running tests inside backend container..."
echo "Command: $PYTEST_CMD"
echo ""

# Run tests in the backend container (dependencies already installed in image)
set +e
docker exec meeting-automation-backend-e2e bash -c "cd /app && $PYTEST_CMD"
TEST_EXIT_CODE=$?
set -e

# Cleanup DEV environment
if [[ "$ENVIRONMENT" == "dev" ]]; then
  echo "Stopping DEV E2E environment..."
  docker compose -f "$PROJECT_ROOT/docker-compose.e2e.yml" down -v
fi

# Exit with pytest's exit code
exit $TEST_EXIT_CODE
