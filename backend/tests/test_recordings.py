import pytest
from httpx import AsyncClient
import os

@pytest.mark.asyncio
async def test_upload_recording(client: AsyncClient):
    # Use real audio file instead of a mock
    audio_path = os.path.join(os.path.dirname(__file__), '../test_audio.wav')
    if not os.path.exists(audio_path):
        pytest.skip(f"Test audio file not found at {audio_path}")

    with open(audio_path, "rb") as f:
        response = await client.post(
            "/api/v1/recordings/upload/1", # meeting_id 1
            files={"file": ("test_audio.wav", f, "audio/wav")}
        )
    
    # Status might be 202 (Accepted) or 201 (Created) or 200 (OK) depending on service
    assert response.status_code in [200, 201, 202]
