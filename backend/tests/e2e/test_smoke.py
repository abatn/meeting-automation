"""
Production Smoke Tests - Critical User Journey Validation.

These tests run ONLY in production after deployment.
They validate the most essential user flows:
1. Health check endpoint
2. Admin authentication
3. Meeting creation
4. Action status updates

Marked with @pytest.mark.smoke to exclude from full E2E suite.
"""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient
from tests.e2e.conftest import EnvironmentConfig, TestEnvironment


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_health_check(e2e_client_no_auth: AsyncClient, environment_config: EnvironmentConfig):
    """Smoke: Production health endpoint returns 200."""
    resp = await e2e_client_no_auth.get("/health")
    assert resp.status_code == 200, f"Health check failed: {resp.text}"
    data = resp.json()
    assert data["status"] == "healthy", f"Health status not healthy: {data}"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_admin_login(e2e_client: AsyncClient, environment_config: EnvironmentConfig):
    """Smoke: Admin can log in and receives access token."""
    # The e2e_client fixture already authenticated, we verify it works
    resp = await e2e_client.get("/api/v1/auth/me")
    assert resp.status_code == 200, f"Failed to get current user: {resp.text}"
    user = resp.json()
    assert "email" in user, "User email missing"
    assert user["email"] == environment_config.test_user_email, f"Wrong user: {user['email']}"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_create_meeting_smoke(e2e_client: AsyncClient, environment_config: EnvironmentConfig):
    """Smoke: Admin can create a meeting."""
    meeting_data = {
        "title": "Production Smoke Test Meeting",
        "description": "Automated production smoke test - DO NOT EDIT",
        "start_time": "2026-04-04T10:00:00",
        "end_time": "2026-04-04T11:00:00",
        "location": "Online",
        "participants": []
    }
    resp = await e2e_client.post("/api/v1/meetings/", json=meeting_data)
    assert resp.status_code == 201, f"Failed to create meeting: {resp.text}"
    meeting = resp.json()
    assert "id" in meeting, "Meeting ID missing"
    assert meeting["title"] == meeting_data["title"]

    # Store meeting ID for subsequent tests (optional cleanup)
    os.environ["SMOKE_TEST_MEETING_ID"] = meeting["id"]


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_action_status_update_smoke(e2e_client: AsyncClient, environment_config: EnvironmentConfig):
    """Smoke: Action status can be updated (critical workflow)."""
    # Get meeting from previous test or create a new one
    meeting_id = os.getenv("SMOKE_TEST_MEETING_ID")
    if not meeting_id:
        # Create a meeting on-the-fly
        meeting_data = {
            "title": "Smoke Action Test Meeting",
            "description": "Temp meeting for smoke test",
            "start_time": "2026-04-04T12:00:00",
            "end_time": "2026-04-04T13:00:00",
            "location": "Test",
            "participants": []
        }
        resp = await e2e_client.post("/api/v1/meetings/", json=meeting_data)
        assert resp.status_code == 201
        meeting_id = resp.json()["id"]

    # Create action
    action_data = {
        "title": "Smoke Test Action",
        "meeting_id": meeting_id,
        "client_id": "test-client-id"
    }
    create_resp = await e2e_client.post("/api/v1/actions/", json=action_data)
    assert create_resp.status_code == 201, f"Failed to create action: {create_resp.text}"
    action_id = create_resp.json()["id"]

    # Update status
    patch_resp = await e2e_client.patch(
        f"/api/v1/actions/{action_id}/status",
        json={"status": "IN_PROGRESS"}
    )
    assert patch_resp.status_code == 200, f"Failed to update action status: {patch_resp.text}"
    updated_action = patch_resp.json()
    assert updated_action["status"] == "IN_PROGRESS", f"Wrong status: {updated_action['status']}"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_api_endpoints_responsive(e2e_client: AsyncClient):
    """Smoke: All critical API endpoints are responsive."""
    endpoints_to_check = [
        "/health",
        "/api/v1/auth/me",
    ]

    for endpoint in endpoints_to_check:
        resp = await e2e_client.get(endpoint)
        assert resp.status_code in [200, 401, 403], f"Endpoint {endpoint} unreachable: {resp.status_code}"
