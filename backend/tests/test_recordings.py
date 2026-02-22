import pytest
from httpx import AsyncClient
import io

@pytest.mark.asyncio
async def test_upload_recording(client: AsyncClient):
    file_content = b"fake audio content"
    file = io.BytesIO(file_content)
    
    response = await client.post(
        "/api/v1/recordings/upload/1", # meeting_id 1
        files={"file": ("test.mp3", file, "audio/mpeg")}
    )
    # Status might be 202 (Accepted) or 201 (Created) depending on service
    assert response.status_code in [201, 202]
