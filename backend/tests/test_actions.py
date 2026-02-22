import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_actions(client: AsyncClient):
    response = await client.get("/api/v1/actions/")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_update_action_status(client: AsyncClient):
    response = await client.patch("/api/v1/actions/1", json={"status": "completed"})
    assert response.status_code in [200, 404]
