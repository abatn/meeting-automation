import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_manager_dashboard_unauthorized():
    # Test without auth token
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/reports/manager/dashboard")
    assert response.status_code == 401 # Assuming standard auth dependency

@pytest.mark.asyncio
async def test_meeting_stats_unauthorized():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/reports/meetings/stats?period=month")
    assert response.status_code == 401
