"""
E2E Tests for Action Status Update with Enum Validation.

These tests connect to actual environments:
- DEV: Local docker-compose.e2e.yml (PostgreSQL, Backend)
- STAGING: Kubernetes staging namespace (meeting-automation-staging)
- PRODUCTION: Kubernetes production namespace (meeting-automation)

Validates:
- Correct enum validation (ActionStatus.PENDING, IN_PROGRESS, COMPLETED, CANCELLED, OVERDUE)
- Rejection of invalid status values ("accepted", "rejected", typos)
- Database integrity (status stored as proper enum)
- n8n webhook payload formation
- ISO 27001 audit logging compliance
"""
import os
import pytest
import pytest_asyncio
import uuid
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.action import Action as ActionModel, ActionStatus
from app.core.config import settings
from tests.e2e.conftest import EnvironmentConfig, TestEnvironment


@pytest_asyncio.fixture(scope="function")
async def test_meeting(e2e_client: AsyncClient, environment_config: EnvironmentConfig) -> dict:
    """
    Fixture: Creates a meeting in the system to be used by action tests.
    Returns the meeting JSON with 'id' field.
    """
    meeting_data = {
        "title": "E2E Test Meeting",
        "description": "Meeting for E2E action testing",
        "start_time": "2026-04-02T10:00:00",
        "end_time": "2026-04-02T11:00:00",
        "location": "Test Location",
        "participants": []
    }
    resp = await e2e_client.post("/api/v1/meetings/", json=meeting_data)
    assert resp.status_code == 201, f"Failed to create meeting: {resp.text}"
    meeting = resp.json()
    return meeting


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_update_action_status_with_valid_enum_values(
    e2e_client: AsyncClient, test_meeting: dict, environment_config: EnvironmentConfig
):
    """E2E: Verify that all valid ActionStatus enum values are accepted and persisted correctly."""
    # Arrange: Create a real action via API using the test meeting
    meeting_id = test_meeting["id"]
    action_data = {
        "title": "E2E Test Action",
        "description": "Testing status enum",
        "meeting_id": meeting_id,
        "client_id": "test-client-id",
        "status": "PENDING",  # Initially pending
        "priority": "medium",
    }

    create_resp = await e2e_client.post("/api/v1/actions/", json=action_data)
    assert create_resp.status_code == 201, f"Failed to create action: {create_resp.text}"
    action = create_resp.json()
    action_id = action["id"]

    # Act & Assert: Test each valid status transition
    valid_statuses = ["IN_PROGRESS", "COMPLETED", "CANCELLED", "OVERDUE"]
    for status in valid_statuses:
        patch_resp = await e2e_client.patch(
            f"/api/v1/actions/{action_id}/status", json={"status": status}
        )
        assert patch_resp.status_code == 200, f"Failed to set status {status}: {patch_resp.text}"

        updated_action = patch_resp.json()
        assert updated_action["status"] == status, f"Status not updated correctly to {status}"

        # Verify via GET endpoint (true E2E: no direct DB access)
        get_resp = await e2e_client.get(f"/api/v1/actions/{action_id}")
        assert get_resp.status_code == 200
        retrieved_action = get_resp.json()
        assert retrieved_action["status"] == status, f"GET endpoint does not reflect status {status}"

    # Finally, test PENDING again (it's also valid as an update)
    patch_resp = await e2e_client.patch(
        f"/api/v1/actions/{action_id}/status", json={"status": "PENDING"}
    )
    assert patch_resp.status_code == 200
    get_resp = await e2e_client.get(f"/api/v1/actions/{action_id}")
    assert get_resp.status_code == 200
    retrieved_action = get_resp.json()
    assert retrieved_action["status"] == "PENDING"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_update_action_status_rejects_invalid_values(
    e2e_client: AsyncClient, db_session: AsyncSession, test_meeting: dict, environment_config: EnvironmentConfig
):
    """E2E: Verify that invalid status values are rejected with clear error messages."""
    # Arrange: Create an action using the test meeting
    meeting_id = test_meeting["id"]
    action_data = {
        "title": "E2E Invalid Status Test",
        "meeting_id": meeting_id,
        "client_id": "test-client-id",
        "status": "PENDING",
    }
    create_resp = await e2e_client.post("/api/v1/actions/", json=action_data)
    assert create_resp.status_code == 201
    action_id = create_resp.json()["id"]

    # Act & Assert: Invalid statuses should return 400
    invalid_statuses = ["accepted", "rejected", "open", "closed", "pendin", "complete", ""]
    for invalid_status in invalid_statuses:
        patch_resp = await e2e_client.patch(
            f"/api/v1/actions/{action_id}/status", json={"status": invalid_status}
        )
        assert patch_resp.status_code == 400, f"Expected 400 for invalid status '{invalid_status}'"
        resp_json = patch_resp.json()
        assert "detail" in resp_json
        # The error message should mention the invalid value and allowed values
        detail = resp_json["detail"]
        assert invalid_status in str(detail) or "Invalid status" in str(detail)

    # Verify DB still has original PENDING status (no change occurred)
    result = await db_session.execute(select(ActionModel).where(ActionModel.id == action_id))
    db_action = result.scalar_one()
    assert db_action.status == ActionStatus.PENDING


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_update_action_status_audit_logging_iso27001(
    e2e_client: AsyncClient, db_session: AsyncSession, db_session_with_audit: AsyncSession, test_meeting: dict, environment_config: EnvironmentConfig
):
    """
    E2E + ISO 27001: Verify that status updates are audit-logged.
    Requirement: All state changes must be recorded in audit_logs table.
    """
    # Skip if production (no direct DB access to production DB)
    if environment_config.env == TestEnvironment.PRODUCTION:
        pytest.skip("Direct DB access not allowed in production environment")

    # Arrange: Create an action using the test meeting
    meeting_id = test_meeting["id"]
    action_data = {
        "title": "Audit Test Action",
        "meeting_id": meeting_id,
        "client_id": "test-client-id",
        "status": "PENDING",
    }
    create_resp = await e2e_client.post("/api/v1/actions/", json=action_data)
    assert create_resp.status_code == 201
    action_id = create_resp.json()["id"]

    # Act: Update status (this should trigger audit logging)
    patch_resp = await e2e_client.patch(
        f"/api/v1/actions/{action_id}/status", json={"status": "COMPLETED"}
    )
    assert patch_resp.status_code == 200

    # Assert: Check audit_log table for the PATCH request
    from app.models.audit_log import AuditLog

    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.table_name == "actions")
        .where(AuditLog.record_id == action_id)
        .order_by(AuditLog.timestamp.desc())
    )
    audit_entries = result.scalars().all()

    assert len(audit_entries) >= 1, "No audit log entry found for status update"
    # The latest audit should be the PATCH update
    latest_audit = audit_entries[0]
    assert latest_audit.action == "PATCH"
    assert latest_audit.table_name == "actions"
    assert latest_audit.record_id == action_id
    # The new_values should contain the updated status (already a dict)
    assert latest_audit.new_values is not None
    new_values = latest_audit.new_values
    assert "status" in new_values
    assert new_values["status"] == "COMPLETED"


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.skipif(
    os.getenv("E2E_TEST") == "true",
    reason="N8N mocking does not work across process boundaries in E2E; use unit tests instead"
)
async def test_update_action_status_n8n_webhook_integration(
    e2e_client: AsyncClient, test_meeting: dict, environment_config: EnvironmentConfig, mock_n8n_action
):
    """
    E2E: Verify that n8n webhook is called when an action status is updated.
    The mock_n8n_action fixture intercepts httpx.AsyncClient.post calls to n8n.
    """
    # Skip n8n integration test in production (real n8n would be called)
    if environment_config.env == TestEnvironment.PRODUCTION:
        pytest.skip("n8n webhook integration not mocked in production smoke tests")

    # Arrange: Create an action using the test meeting
    meeting_id = test_meeting["id"]
    action_data = {
        "title": "n8n Webhook Test Action",
        "meeting_id": meeting_id,
        "client_id": "test-client-id",
        "status": "PENDING",
    }
    create_resp = await e2e_client.post("/api/v1/actions/", json=action_data)
    assert create_resp.status_code == 201
    action = create_resp.json()
    action_id = action["id"]
    action_title = action["title"]

    # Act: Update status
    patch_resp = await e2e_client.patch(
        f"/api/v1/actions/{action_id}/status", json={"status": "IN_PROGRESS"}
    )
    assert patch_resp.status_code == 200

    # Assert: n8n webhook was called via httpx.AsyncClient.post (mocked by fixture)
    assert mock_n8n_action.await_count >= 1, f"n8n webhook was not called (await_count={mock_n8n_action.await_count})"

    # Verify payload structure (optional, but ensures correct data sent)
    call_args = mock_n8n_action.call_args
    if call_args:
        # Called with (url, json=payload) as positional or keyword args
        url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url")
        payload = call_args.kwargs.get("json")
        assert payload is not None, "No JSON payload sent"
        assert payload.get("event") == "action.status_updated"
        assert payload.get("action_id") == action_id
        assert payload.get("status") == "IN_PROGRESS"
        assert payload.get("title") == action_title


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_action_status_never_stores_invalid_enum_in_db(
    e2e_client: AsyncClient, db_session: AsyncSession, test_meeting: dict, environment_config: EnvironmentConfig
):
    """
    E2E Database Integrity: Even if API validation were bypassed, the DB should reject invalid enum values.
    This tests the SQLAlchemy enum constraint at the database level (PostgreSQL ENUM type).
    """
    # This test assumes direct DB access to try inserting an invalid status (bypassing API)
    # Skip if using SQLite test DB or in production (SQLite doesn't enforce ENUM strictly)
    if "sqlite" in settings.DATABASE_URL:
        pytest.skip("SQLite does not enforce ENUM constraints strictly")

    # Skip in production - direct DB access not allowed
    if environment_config.env == TestEnvironment.PRODUCTION:
        pytest.skip("Direct DB access not allowed in production environment")

    # Use the test meeting that exists in DB
    meeting_id = test_meeting["id"]

    # Try to insert an action with an invalid status directly
    invalid_action_id = str(uuid.uuid4())
    invalid_action = ActionModel(
        id=invalid_action_id,
        client_id="test-client-id",
        meeting_id=meeting_id,
        title="Invalid Status Action",
        status="accepted",  # This is NOT a valid ActionStatus member
    )
    db_session.add(invalid_action)

    # This should raise an IntegrityError from PostgreSQL because 'accepted' is not in the enum
    with pytest.raises(Exception):  # Could be IntegrityError or similar
        await db_session.commit()

    await db_session.rollback()

    # Verify that no such action exists in DB with invalid status
    result = await db_session.execute(
        select(ActionModel).where(ActionModel.id == invalid_action_id)
    )
    assert result.scalar_one_or_none() is None
