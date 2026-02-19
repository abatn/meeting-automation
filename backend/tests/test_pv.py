import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.pv import PV
from backend.app.models.meeting import Meeting
from backend.app.models.transcription import Transcription
from backend.app.models.recording import Recording
from backend.app.schemas.pv import PVCreate, PVUpdate
from datetime import datetime, timezone # Import timezone
import json # Import json
from backend.app.core.security import create_access_token_for_user # Import create_access_token_for_user
from backend.app.models.user import User, UserRole # Import User and UserRole
from backend.app.models.pv import PV, PVStatus # Import PV and PVStatus
from backend.app.schemas.pv import PVUpdate, PVResponse, PVValidationResponse # Import schemas

# Mock data for Mistral API responses
MOCK_PV_CONTENT = "Mocked PV content."
MOCK_DECISIONS = ["Decision 1.", "Decision 2."]
MOCK_ACTION_POINTS = [
    "Action 1 - Assigned to User A - Due by 2023-01-10",
    "Action 2 - Assigned to User B - Due by 2023-01-15"
]
MOCK_SUMMARY = "Mocked summary of the meeting."

@pytest.mark.asyncio
async def test_generate_pv(client: AsyncClient, auth_headers: dict, test_meeting: Meeting, mock_mistral, db_session: AsyncSession, test_user):
    # Create recording
    recording = Recording(
        meeting_id=test_meeting.id,
        duration=60,
        file_path="/tmp/test.mp3",
        file_size=1024,
        uploader_id=test_user.id
    )
    db_session.add(recording)
    await db_session.commit()
    await db_session.refresh(recording)

    # Create transcription
    transcription = Transcription(
        meeting_id=test_meeting.id,
        recording_id=recording.id,
        transcribed_text="Test transcription content",
        language="fr",
        status="COMPLETED",
        created_by_id=test_user.id
    )
    db_session.add(transcription)
    await db_session.commit()
    await db_session.refresh(transcription)

    # Mock return value matching the structure expected from MistralClient.generate_pv
    mock_mistral["generate_pv"].return_value = MOCK_PV_CONTENT
    mock_mistral["extract_decisions"].return_value = MOCK_DECISIONS
    mock_mistral["extract_action_items"].return_value = MOCK_ACTION_POINTS

    # Request body for PV generation
    pv_generate_data = {
        "transcription_id": transcription.id,
        "template": "standard"
    }

    response = await client.post(
        f"/api/v1/pv/{test_meeting.id}/generate",
        json=pv_generate_data,
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meeting_id"] == test_meeting.id
    assert data["content"] == MOCK_PV_CONTENT  # Use MOCK_PV_CONTENT
    assert "id" in data
    assert data["status"] == PVStatus.DRAFT
    assert data["decisions"] == MOCK_DECISIONS  # Assert decisions
    assert data["action_points"] == MOCK_ACTION_POINTS  # Assert action_points

@pytest.mark.asyncio
async def test_get_pv(client: AsyncClient, auth_headers: dict, test_pv: PV):
    response = await client.get(
        f"/api/v1/pv/{test_pv.id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_pv.id
    assert data["meeting_id"] == test_pv.meeting_id
    assert data["content"] == test_pv.content
    assert data["status"] == PVStatus.DRAFT
    assert data["decisions"] == test_pv.decisions # The service layer will have converted JSONEncodedText to list
    assert data["action_points"] == test_pv.action_points # The service layer will have converted JSONEncodedText to list
    assert data["generated_by_id"] == test_pv.generated_by_id

@pytest.mark.asyncio
async def test_update_pv(client: AsyncClient, auth_headers: dict, test_pv: PV):
    update_data = {
        "content": "Updated PV content.",
        "decisions": ["Updated Decision 1", "Updated Decision 2"],
        "action_points": ["Updated Action 1"],
        "title": "Updated Test PV Title"
    }
    response = await client.put(
        f"/api/v1/pv/{test_pv.id}",
        json=update_data,
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_pv.id
    assert data["content"] == "Updated PV content."
    assert data["decisions"] == ["Updated Decision 1", "Updated Decision 2"]
    assert data["action_points"] == ["Updated Action 1"]
    assert data["title"] == "Updated Test PV Title"
    assert data["status"] == PVStatus.DRAFT

@pytest.mark.asyncio
async def test_validate_pv_as_dg(client: AsyncClient, dg_headers: dict, test_pv: PV, db_session: AsyncSession):
    response = await client.post(f"/api/v1/pv/{test_pv.id}/validate", headers=dg_headers, json={"comment": "LGTM"})
    assert response.status_code == 200
    
    # Manually trigger a refresh from the database to get the updated state
    await db_session.refresh(test_pv)

    # The response should now match the model-derived schema
    expected_data = PVValidationResponse.model_validate(test_pv).model_dump(by_alias=True)
    actual_data = response.json()

    # The computed field `isValidated` should be True
    assert actual_data["isValidated"] is True
    assert actual_data["status"] == PVStatus.VALIDATED
    assert actual_data["validation_comment"] == "LGTM"

@pytest.mark.asyncio
async def test_validate_pv_as_non_dg(client: AsyncClient, auth_headers: dict, test_pv: PV):
    response = await client.post(f"/api/v1/pv/{test_pv.id}/validate", headers=auth_headers, json={"comment": "LGTM"})
    assert response.status_code == 403
    assert "Only DGs can validate PVs" in response.json()["detail"]

@pytest.mark.asyncio
async def test_delete_pv_as_admin(client: AsyncClient, admin_headers: dict, test_pv: PV):
    response = await client.delete(f"/api/v1/pv/{test_pv.id}", headers=admin_headers)
    assert response.status_code == 204

    # Verify PV is actually deleted
    response = await client.get(f"/api/v1/pv/{test_pv.id}", headers=admin_headers)
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_delete_pv_as_non_admin(client: AsyncClient, auth_headers: dict, test_pv: PV):
    response = await client.delete(f"/api/v1/pv/{test_pv.id}", headers=auth_headers)
    assert response.status_code == 403
    assert "Only Admins can delete PVs" in response.json()["detail"]

@pytest.mark.asyncio
async def test_mistral_api_error_handling(client: AsyncClient, auth_headers: dict, test_meeting: Meeting, mock_mistral, db_session: AsyncSession, test_user):
    # Create recording
    recording = Recording(
        meeting_id=test_meeting.id,
        duration=60,
        file_path="/tmp/test.mp3",
        file_size=1024,
        uploader_id=test_user.id
    )
    db_session.add(recording)
    await db_session.commit()
    await db_session.refresh(recording)

    # Create transcription
    transcription = Transcription(
        meeting_id=test_meeting.id,
        recording_id=recording.id,
        transcribed_text="Test transcription content",
        language="fr",
        status="COMPLETED",
        created_by_id=test_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(transcription)
    await db_session.commit()
    await db_session.refresh(transcription)

    mock_mistral["generate_pv"].side_effect = Exception("Mistral API is down")

    pv_generate_data = {
        "transcription_id": transcription.id,
        "template": "standard"
    }

    response = await client.post(
        f"/api/v1/pv/{test_meeting.id}/generate",
        json=pv_generate_data,
        headers=auth_headers
    )
    assert response.status_code == 500
    assert "Failed to generate PV: Mistral API is down" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_pv_by_meeting(client: AsyncClient, auth_headers: dict, test_meeting: Meeting, test_pv: PV):
    response = await client.get(f"/api/v1/pv/meeting/{test_meeting.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["id"] == test_pv.id
    assert data[0]["meeting_id"] == test_pv.meeting_id
    assert data[0]["content"] == test_pv.content
    assert data[0]["status"] == PVStatus.DRAFT
    assert data[0]["decisions"] == test_pv.decisions # The service layer will have converted JSONEncodedText to list
    assert data[0]["action_points"] == test_pv.action_points # The service layer will have converted JSONEncodedText to list
    assert data[0]["generated_by_id"] == test_pv.generated_by_id
