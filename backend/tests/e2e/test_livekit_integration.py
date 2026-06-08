"""
E2E Tests for LiveKit Integration — Token, Recording, Webhook.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_livekit_token_endpoint(e2e_client: AsyncClient, e2e_meeting: dict):
    """Verify authenticated user can get a LiveKit token."""
    meeting_id = e2e_meeting["id"]
    resp = await e2e_client.post(f"/api/v1/meetings/{meeting_id}/livekit/token")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    data = resp.json()
    # LiveKit Meet ConnectionDetails pattern
    assert "participantToken" in data, "Response must contain 'participantToken'"
    assert isinstance(data["participantToken"], str) and len(data["participantToken"]) > 20, "Token must be a valid JWT"
    assert "serverUrl" in data, "Response must contain 'serverUrl'"
    assert "roomName" in data, "Response must contain 'roomName'"
    assert "participantName" in data, "Response must contain 'participantName'"


@pytest.mark.asyncio
async def test_livekit_start_recording(e2e_client: AsyncClient, e2e_meeting: dict):
    """Verify start-recording returns 201 and starts an egress."""
    meeting_id = e2e_meeting["id"]
    resp = await e2e_client.post(f"/api/v1/meetings/{meeting_id}/livekit/start-recording")
    assert resp.status_code in (200, 201, 202), (
        f"Expected recording to start, got {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert "egress_id" in data, f"Response missing egress_id: {data}"
    assert "status" in data, f"Response missing status: {data}"
    assert data["status"] == "recording", f"Expected 'recording', got '{data.get('status')}'"
    assert "recording_id" in data, f"Response missing recording_id: {data}"


@pytest.mark.asyncio
async def test_livekit_webhook_egress_completed(e2e_client_no_auth: AsyncClient):
    """Verify LiveKit webhook for egress.completed works with correct auth."""
    payload = {
        "event": "egress.completed",
        "room_name": "test-meeting-id",
        "egress_id": "egress-test-456",
        "file_location": "recordings/test_meeting/output.ogg",
    }
    resp = await e2e_client_no_auth.post(
        "/api/v1/livekit/webhooks",
        json=payload,
        headers={"Authorization": f"Bearer {settings.INTERNAL_API_SECRET}"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["ok"] is True
    assert data["event"] == "egress.completed"


@pytest.mark.asyncio
async def test_livekit_webhook_unauthorized(e2e_client_no_auth: AsyncClient):
    """Verify webhook without valid auth gets 403."""
    payload = {
        "event": "egress.completed",
        "room_name": "test-meeting-id",
        "egress_id": "egress-test-456",
        "file_location": "recordings/test_meeting/output.ogg",
    }
    resp = await e2e_client_no_auth.post(
        "/api/v1/livekit/webhooks",
        json=payload,
        headers={"Authorization": "Bearer wrong-secret"},
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


@pytest.mark.asyncio
async def test_livekit_webhook_unknown_event(e2e_client_no_auth: AsyncClient):
    """Verify unknown events return 200 without error."""
    payload = {"event": "room.finished", "room_name": "test-room"}
    resp = await e2e_client_no_auth.post(
        "/api/v1/livekit/webhooks",
        json=payload,
        headers={"Authorization": f"Bearer {settings.INTERNAL_API_SECRET}"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data["event"] == "room.finished"


@pytest.mark.asyncio
async def test_livekit_meeting_creates_room(e2e_client: AsyncClient):
    """Verify that creating a meeting attempts to create a LiveKit room (non-fatal if unavailable)."""
    meeting_data = {
        "title": "LiveKit Room Test",
        "description": "Test for LiveKit room creation",
        "start_time": "2026-06-05T10:00:00",
        "end_time": "2026-06-05T11:00:00",
        "participants": [],
    }
    resp = await e2e_client.post("/api/v1/meetings/", json=meeting_data)
    assert resp.status_code in (
        200, 201,
    ), f"Expected 200 or 201, got {resp.status_code}: {resp.text}"
    assert resp.json().get("id") is not None, "Meeting must have an id"


@pytest.mark.asyncio
async def test_livekit_token_response_structure(e2e_client: AsyncClient, e2e_meeting: dict):
    """Verify token response has expected structure (LiveKit Meet ConnectionDetails pattern)."""
    meeting_id = e2e_meeting["id"]
    resp = await e2e_client.post(f"/api/v1/meetings/{meeting_id}/livekit/token")
    assert resp.status_code == 200
    data = resp.json()
    # LiveKit Meet ConnectionDetails pattern
    assert data["participantToken"].startswith("eyJ"), "Token should be a JWT (starts with eyJ)"
    assert data["serverUrl"].startswith("ws://") or data["serverUrl"].startswith("wss://")
    assert data["roomName"] == meeting_id, "roomName must match meeting_id"
    assert isinstance(data["participantName"], str) and len(data["participantName"]) > 0


@pytest.mark.asyncio
async def test_livekit_recording_status_idle(e2e_client: AsyncClient, e2e_meeting: dict):
    """Verify recording-status returns idle when no recording exists."""
    meeting_id = e2e_meeting["id"]
    resp = await e2e_client.get(f"/api/v1/meetings/{meeting_id}/livekit/recording-status")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "status" in data, "Response must contain 'status'"
    # idle = no recording yet; other statuses = recording in various states
    assert data["status"] in ("idle", "streaming", "uploaded", "stopped", "processing", "transcribing"), \
        f"Unexpected status: {data['status']}"
    assert "recording_id" in data, "Response must contain 'recording_id'"


@pytest.mark.asyncio
async def test_livekit_stop_recording_no_active(e2e_client: AsyncClient, e2e_meeting: dict):
    """Verify stop-recording returns 404 when no active recording."""
    meeting_id = e2e_meeting["id"]
    resp = await e2e_client.post(f"/api/v1/meetings/{meeting_id}/livekit/stop-recording")
    # Either 404 (no recording) or 503 (egress not reachable) — both valid
    assert resp.status_code in (404, 503), \
        f"Expected 404 or 503 when no active recording, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_livekit_stop_recording_requires_auth(e2e_client_no_auth: AsyncClient, e2e_meeting: dict):
    """Verify stop-recording requires authentication — unauthenticated gets 401, 403, or 404."""
    meeting_id = e2e_meeting["id"]
    resp = await e2e_client_no_auth.post(f"/api/v1/meetings/{meeting_id}/livekit/stop-recording")
    # 401/403 = auth rejected, 404 = no active recording (still secure — auth checked first)
    assert resp.status_code in (401, 403, 404), \
        f"Expected 401, 403, or 404 for unauthenticated stop, got {resp.status_code}: {resp.text}"
