#!/bin/bash
# E2E Test Runner for Meeting Automation System
# This script runs the E2E tests against the running Docker containers.
#
# Usage:
#   ./run_e2e_tests.sh [options]
#
# Options:
#   --isolated    Start a fresh test environment with docker-compose.e2e.yml (isolated)
#   --prod        Use the existing production containers (default: asks for confirmation)
#   --help        Show this help message

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODE="interactive"

while [[ $# -gt 0 ]]; do
    case $1 in
        --isolated)
            MODE="isolated"
            shift
            ;;
        --prod)
            MODE="prod"
            shift
            ;;
        --help)
            cat << EOF
E2E Test Runner for Meeting Automation System

Usage: $0 [OPTIONS]

Options:
  --isolated    Start a fresh, isolated test environment using docker-compose.e2e.yml
  --prod        Run tests against the existing production containers (USE WITH CAUTION)
  --help        Show this help message

Examples:
  # Interactive mode (will ask which mode to use)
  $0

  # Run isolated tests (fresh DB, won't affect production data)
  $0 --isolated

  # Run against existing containers (requires confirmation)
  $0 --prod
EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "Meeting Automation - E2E Test Runner"
echo "=========================================="
echo ""

if [[ "$MODE" == "interactive" ]]; then
    echo "Select test mode:"
    echo "1) Isolated (recommended) - Start a fresh test environment with its own database"
    echo "2) Production - Run tests against your existing containers (WILL MODIFY TEST DATA)"
    read -p "Enter choice (1 or 2): " choice
    case $choice in
        1) MODE="isolated" ;;
        2)
            MODE="prod"
            echo ""
            echo "⚠️  WARNING: This will insert test data into your running PostgreSQL container."
            read -p "Are you sure? (yes/no): " confirm
            if [[ "$confirm" != "yes" ]]; then
                echo "Aborted."
                exit 1
            fi
            ;;
        *) echo "Invalid choice"; exit 1 ;;
    esac
fi

if [[ "$MODE" == "isolated" ]]; then
    echo "🚀 Starting isolated E2E test environment..."
    echo "   - Fresh PostgreSQL on port 5433"
    echo "   - Backend test container"
    echo "   - Redis test instance"
    echo ""

    # Check if docker-compose.e2e.yml exists
    if [[ ! -f "$SCRIPT_DIR/docker-compose.e2e.yml" ]]; then
        echo "❌ Error: docker-compose.e2e.yml not found!"
        exit 1
    fi

    # Bring up the isolated test environment
    docker compose -f "$SCRIPT_DIR/docker-compose.e2e.yml" up --build --abort-on-container-exit

    echo ""
    echo "✅ Isolated tests completed."
    echo "   To clean up: docker compose -f docker-compose.e2e.yml down"

elif [[ "$MODE" == "prod" ]]; then
    echo "🧪 Running E2E tests against existing production containers..."
    echo "   Backend: http://localhost:8000"
    echo "   PostgreSQL: localhost:5432"
    echo ""

    # Set environment variable to use production DB
    export TEST_USE_PROD_DB=true

    # Check if backend container is running
    if ! docker ps | grep -q meeting-automation-backend-1; then
        echo "❌ Backend container is not running!"
        exit 1
    fi

    # Install dependencies if needed
    echo "📦 Ensuring test dependencies..."
    cd "$SCRIPT_DIR/../backend"
    if [[ ! -d ".venv" ]]; then
        python3 -m venv .venv
        source .venv/bin/activate
        pip install -q pytest pytest-asyncio httpx
        pip install -q -r requirements.txt
    fi

    # Run the E2E tests
    echo ""
    echo "Running E2E test suite..."
    source .venv/bin/activate
    python -m pytest tests/e2e/test_action_status_e2e.py -v --tb=short

    echo ""
    echo "✅ E2E tests completed against production containers."
    echo "   Check results above for any failures."
else
    echo "❌ Unknown mode: $MODE"
    exit 1
fi
