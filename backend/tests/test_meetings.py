import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_meeting(client: AsyncClient, test_meeting_data):
    # Mock Auth header would be needed in real scenario
    response = await client.post("/api/v1/meetings/", json=test_meeting_data)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == test_meeting_data["title"]

@pytest.mark.asyncio
async def test_get_meetings(client: AsyncClient):
    response = await client.get("/api/v1/meetings/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
