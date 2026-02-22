import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_transcription_status(client: AsyncClient):
    response = await client.get("/api/v1/transcriptions/1")
    # If not exists 404, if exists 200
    assert response.status_code in [200, 404]

@pytest.mark.asyncio
async def test_mock_whisper_callback(client: AsyncClient):
    # Simulate Whisper service calling our webhook
    payload = {
        "recording_id": 1,
        "text": "Bonjour, ceci est un test de transcription.",
        "language": "fr",
        "status": "completed"
    }
    response = await client.post("/api/v1/transcriptions/webhook", json=payload)
    assert response.status_code == 200
