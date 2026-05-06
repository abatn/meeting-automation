#!/bin/bash

################################################################################
# N8N Workflow Test Suite
# Comprehensive testing for all n8n workflows in the pipeline
# Tests: Webhook responses, error handling, retries, env var support
################################################################################

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
N8N_BASE_URL="${N8N_BASE_URL:-http://localhost:5678}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
TEST_RESULTS_DIR="${TEST_RESULTS_DIR:-./n8n/tests/results}"

# Ensure test results directory exists
mkdir -p "$TEST_RESULTS_DIR"

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

################################################################################
# Helper Functions
################################################################################

log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
}

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

assert_http_status() {
    local http_code=$1
    local expected=$2
    local test_name=$3
    
    ((TESTS_RUN++))
    
    if [ "$http_code" -eq "$expected" ]; then
        log_pass "$test_name (HTTP $http_code)"
    else
        log_fail "$test_name (Expected HTTP $expected, got $http_code)"
    fi
}

assert_json_field() {
    local json=$1
    local field=$2
    local expected_value=$3
    local test_name=$4
    
    ((TESTS_RUN++))
    
    local actual=$(echo "$json" | jq -r ".$field // empty" 2>/dev/null)
    
    if [ "$actual" = "$expected_value" ]; then
        log_pass "$test_name (field '$field' = '$expected_value')"
    else
        log_fail "$test_name (field '$field' expected '$expected_value', got '$actual')"
    fi
}

assert_json_exists() {
    local json=$1
    local field=$2
    local test_name=$3
    
    ((TESTS_RUN++))
    
    if echo "$json" | jq -e ".$field" > /dev/null 2>&1; then
        log_pass "$test_name (field '$field' exists)"
    else
        log_fail "$test_name (field '$field' does not exist)"
    fi
}

################################################################################
# Workflow Tests
################################################################################

test_audio_uploaded_webhook() {
    log_test "Testing audio-uploaded workflow"
    
    local webhook_path="webhook/audio-uploaded"
    local webhook_url="${N8N_BASE_URL}/${webhook_path}"
    
    local request_payload='{
        "meeting_id": "test-meeting-001",
        "audio_url": "https://example.com/audio.mp3",
        "duration_seconds": 3600
    }'
    
    log_info "POST $webhook_url"
    log_info "Payload: $request_payload"
    
    local response=$(curl -s -w "\n%{http_code}" \
        -X POST "$webhook_url" \
        -H "Content-Type: application/json" \
        -d "$request_payload")
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    assert_http_status "$http_code" 200 "audio-uploaded returns 200 OK"
    assert_json_field "$body" "status" "transcription_started" "audio-uploaded response has correct status"
    assert_json_exists "$body" "meeting_id" "audio-uploaded response includes meeting_id"
    assert_json_exists "$body" "timestamp" "audio-uploaded response includes timestamp"
    
    # Test error handling - missing required field
    local error_payload='{
        "audio_url": "https://example.com/audio.mp3"
    }'
    
    local error_response=$(curl -s -w "\n%{http_code}" \
        -X POST "$webhook_url" \
        -H "Content-Type: application/json" \
        -d "$error_payload")
    
    local error_http_code=$(echo "$error_response" | tail -n1)
    
    # Should still return 200 due to error handling, but with error status
    assert_http_status "$error_http_code" 200 "audio-uploaded handles missing fields gracefully"
}

test_meeting_created_webhook() {
    log_test "Testing meeting-created workflow"
    
    local webhook_path="webhook/meeting-created"
    local webhook_url="${N8N_BASE_URL}/${webhook_path}"
    
    local request_payload='{
        "body": {
            "meeting_id": "test-meeting-002",
            "title": "Team Standup",
            "start_time": "2026-05-06T10:00:00Z",
            "attendees": ["alice@example.com", "bob@example.com"]
        }
    }'
    
    log_info "POST $webhook_url"
    
    local response=$(curl -s -w "\n%{http_code}" \
        -X POST "$webhook_url" \
        -H "Content-Type: application/json" \
        -d "$request_payload")
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    assert_http_status "$http_code" 200 "meeting-created returns 200 OK"
    assert_json_field "$body" "status" "invitations_sent" "meeting-created response has correct status"
    assert_json_field "$body" "attendees_count" "2" "meeting-created reports correct attendee count"
}

test_transcription_completed_webhook() {
    log_test "Testing transcription-completed workflow"
    
    local webhook_path="webhook/transcription-completed"
    local webhook_url="${N8N_BASE_URL}/${webhook_path}"
    
    local request_payload='{
        "body": {
            "meeting_id": "test-meeting-003",
            "transcription_id": "trans-001",
            "content": "Meeting transcript content here",
            "duration": 3600
        }
    }'
    
    log_info "POST $webhook_url"
    
    local response=$(curl -s -w "\n%{http_code}" \
        -X POST "$webhook_url" \
        -H "Content-Type: application/json" \
        -d "$request_payload")
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    assert_http_status "$http_code" 200 "transcription-completed returns 200 OK"
    assert_json_field "$body" "status" "email_sent" "transcription-completed response has correct status"
}

test_pv_validated_webhook() {
    log_test "Testing pv-validated workflow"
    
    local webhook_path="webhook/pv-validated"
    local webhook_url="${N8N_BASE_URL}/${webhook_path}"
    
    local request_payload='{
        "body": {
            "meeting_id": "test-meeting-004",
            "pv_id": "pv-001",
            "status": "validated",
            "version": 1
        }
    }'
    
    log_info "POST $webhook_url"
    
    local response=$(curl -s -w "\n%{http_code}" \
        -X POST "$webhook_url" \
        -H "Content-Type: application/json" \
        -d "$request_payload")
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    assert_http_status "$http_code" 200 "pv-validated returns 200 OK"
    assert_json_field "$body" "status" "pv_distributed" "pv-validated response has correct status"
}

test_user_invited_webhook() {
    log_test "Testing user-invited workflow"
    
    local webhook_path="webhook/user-invited"
    local webhook_url="${N8N_BASE_URL}/${webhook_path}"
    
    local request_payload='{
        "body": {
            "email": "newuser@example.com",
            "full_name": "John Doe",
            "company_name": "Acme Corp",
            "activation_link": "https://example.com/activate/token123"
        }
    }'
    
    log_info "POST $webhook_url"
    
    local response=$(curl -s -w "\n%{http_code}" \
        -X POST "$webhook_url" \
        -H "Content-Type: application/json" \
        -d "$request_payload")
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    assert_http_status "$http_code" 200 "user-invited returns 200 OK"
    assert_json_field "$body" "status" "invitation_sent" "user-invited response has correct status"
    assert_json_exists "$body" "email" "user-invited response includes email"
}

test_meeting_status_changed_webhook() {
    log_test "Testing meeting-status-changed webhook"
    
    local webhook_path="webhook/meeting-status-changed"
    local webhook_url="${N8N_BASE_URL}/${webhook_path}"
    
    local request_payload='{
        "body": {
            "meeting_id": "test-meeting-005",
            "title": "Board Meeting",
            "status": "in_progress",
            "previous_status": "planned",
            "start_time": "2026-05-06T14:00:00Z",
            "attendees": ["executive1@example.com", "executive2@example.com"]
        }
    }'
    
    log_info "POST $webhook_url"
    
    local response=$(curl -s -w "\n%{http_code}" \
        -X POST "$webhook_url" \
        -H "Content-Type: application/json" \
        -d "$request_payload")
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    assert_http_status "$http_code" 200 "meeting-status-changed returns 200 OK"
    assert_json_field "$body" "status" "notification_sent" "meeting-status-changed response has correct status"
}

test_daily_reminders_cron() {
    log_test "Testing daily-reminders cron workflow"
    
    # Note: Can't trigger cron directly, but can verify configuration
    log_info "Checking daily-reminders workflow configuration..."
    
    # Verify the workflow file contains cron trigger
    if grep -q '"type": "n8n-nodes-base.cron"' /home/opc/meeting-automation/n8n/workflows/daily-reminders.json; then
        log_pass "daily-reminders has cron trigger configured"
        ((TESTS_RUN++))
    else
        log_fail "daily-reminders cron trigger not found"
        ((TESTS_RUN++))
    fi
    
    # Verify WhatsApp node exists
    if grep -q 'WhatsApp Reminder' /home/opc/meeting-automation/n8n/workflows/daily-reminders.json; then
        log_pass "daily-reminders has WhatsApp notification node"
        ((TESTS_RUN++))
    else
        log_fail "daily-reminders WhatsApp node not found"
        ((TESTS_RUN++))
    fi
}

test_error_handling() {
    log_test "Testing error handling in workflows"
    
    # Test with invalid JSON
    local webhook_url="${N8N_BASE_URL}/webhook/audio-uploaded"
    
    local response=$(curl -s -w "\n%{http_code}" \
        -X POST "$webhook_url" \
        -H "Content-Type: application/json" \
        -d "invalid json")
    
    local http_code=$(echo "$response" | tail -n1)
    
    # Should still return response due to error handling
    assert_http_status "$http_code" 200 "Workflow handles invalid JSON gracefully"
}

test_environment_variable_support() {
    log_test "Testing environment variable support"
    
    # Check if workflows use environment variables for URLs
    if grep -q '\$env\[' /home/opc/meeting-automation/n8n/workflows/*.json; then
        log_pass "Workflows use environment variables for configuration"
        ((TESTS_RUN++))
    else
        log_fail "Workflows don't use environment variables"
        ((TESTS_RUN++))
    fi
    
    # Check for BACKEND_URL variable
    if grep -q 'BACKEND_URL' /home/opc/meeting-automation/n8n/workflows/*.json; then
        log_pass "Workflows have BACKEND_URL environment variable support"
        ((TESTS_RUN++))
    else
        log_fail "BACKEND_URL environment variable not found"
        ((TESTS_RUN++))
    fi
}

test_response_nodes() {
    log_test "Testing webhook response nodes"
    
    # Check each workflow has respond-to-webhook nodes
    for workflow in audio-uploaded meeting-created transcription-completed pv-validated user-invited meeting-status-changed; do
        if grep -q 'respondToWebhook' /home/opc/meeting-automation/n8n/workflows/${workflow}.json; then
            log_pass "$workflow has respond-to-webhook node"
            ((TESTS_RUN++))
        else
            log_fail "$workflow missing respond-to-webhook node"
            ((TESTS_RUN++))
        fi
    done
}

test_retry_configuration() {
    log_test "Testing retry configuration"
    
    # Check for maxRetries in HTTP request nodes
    local retry_count=$(grep -c '"maxRetries"' /home/opc/meeting-automation/n8n/workflows/*.json || true)
    
    if [ "$retry_count" -gt 0 ]; then
        log_pass "Workflows have retry configuration (found $retry_count instances)"
        ((TESTS_RUN++))
    else
        log_fail "No retry configuration found in workflows"
        ((TESTS_RUN++))
    fi
    
    # Check for exponential backoff
    if grep -q '"retryWait": "exponential"' /home/opc/meeting-automation/n8n/workflows/*.json; then
        log_pass "Workflows use exponential backoff for retries"
        ((TESTS_RUN++))
    else
        log_fail "Exponential backoff not configured"
        ((TESTS_RUN++))
    fi
}

################################################################################
# Test Summary
################################################################################

print_summary() {
    echo ""
    echo "================================================================================"
    echo "N8N Workflow Test Summary"
    echo "================================================================================"
    echo -e "Tests Run:    ${BLUE}$TESTS_RUN${NC}"
    echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
    echo "================================================================================"
    
    if [ "$TESTS_FAILED" -eq 0 ]; then
        echo -e "${GREEN}✓ All tests passed!${NC}"
        return 0
    else
        echo -e "${RED}✗ Some tests failed${NC}"
        return 1
    fi
}

################################################################################
# Main Execution
################################################################################

main() {
    echo "N8N Workflow Test Suite"
    echo "======================="
    echo "N8N Base URL: $N8N_BASE_URL"
    echo "Backend URL:  $BACKEND_URL"
    echo ""
    
    # Run all tests
    test_audio_uploaded_webhook
    echo ""
    test_meeting_created_webhook
    echo ""
    test_transcription_completed_webhook
    echo ""
    test_pv_validated_webhook
    echo ""
    test_user_invited_webhook
    echo ""
    test_meeting_status_changed_webhook
    echo ""
    test_daily_reminders_cron
    echo ""
    test_error_handling
    echo ""
    test_environment_variable_support
    echo ""
    test_response_nodes
    echo ""
    test_retry_configuration
    echo ""
    
    # Print summary
    print_summary
}

# Run main function
main "$@"
exit $?
