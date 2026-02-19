import pytest
from httpx import AsyncClient
from backend.app.schemas.transcription import TranscriptionCreate, TranscriptionUpdate, TranscriptionStatus

@pytest.mark.asyncio
async def test_create_transcription(client: AsyncClient, auth_headers: dict, test_recording, mock_whisper):
    transcription_data = {
        "recording_id": test_recording.id,
        "language": "en",
        "enable_diarization": True
    }
    response = await client.post("/api/v1/transcriptions/", json=transcription_data, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["recording_id"] == test_recording.id
    assert data["status"] in ["PENDING", "COMPLETED"]
    assert "id" in data

@pytest.mark.asyncio
async def test_get_transcriptions(client: AsyncClient, auth_headers: dict, test_transcription, test_meeting):
    response = await client.get(f"/api/v1/transcriptions/?meeting_id={test_meeting.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["id"] == test_transcription.id

@pytest.mark.asyncio
async def test_get_transcription(client: AsyncClient, auth_headers: dict, test_transcription):
    response = await client.get(f"/api/v1/transcriptions/{test_transcription.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_transcription.id
    assert data["transcribed_text"] == test_transcription.transcribed_text

@pytest.mark.asyncio
async def test_update_transcription(client: AsyncClient, auth_headers: dict, test_transcription):
    update_data = {"transcribed_text": "Updated transcription text"}
    response = await client.patch(f"/api/v1/transcriptions/{test_transcription.id}", json=update_data, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["transcribed_text"] == "Updated transcription text"

@pytest.mark.asyncio
async def test_delete_transcription(client: AsyncClient, auth_headers: dict, test_transcription):
    response = await client.delete(f"/api/v1/transcriptions/{test_transcription.id}", headers=auth_headers)
    assert response.status_code == 204
    
    # Verify deletion
    response = await client.get(f"/api/v1/transcriptions/{test_transcription.id}", headers=auth_headers)
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_export_transcription_txt(client: AsyncClient, auth_headers: dict, test_transcription):
    response = await client.get(f"/api/v1/transcriptions/{test_transcription.id}/export?format=txt", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert test_transcription.transcribed_text in response.text

@pytest.mark.asyncio
async def test_get_transcription_status(client: AsyncClient, auth_headers: dict, test_transcription):
    response = await client.get(f"/api/v1/transcriptions/{test_transcription.id}/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == test_transcription.status.value