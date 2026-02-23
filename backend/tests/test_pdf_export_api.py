import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_pdf_download_unauthorized():
    # Attempting to download PDF without authorization
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/pv/123/pdf")
    assert response.status_code == 401
