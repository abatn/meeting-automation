import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_generate_pv(client: AsyncClient):
    response = await client.post("/api/v1/pv/generate/1")
    assert response.status_code in [200, 202, 404]

@pytest.mark.asyncio
async def test_validate_pv(client: AsyncClient):
    response = await client.post("/api/v1/pv/1/approve")
    assert response.status_code in [200, 404]
