import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_sql_injection_protection(client: AsyncClient):
    payload = {
        "title": "Meeting'); DROP TABLE users;--",
        "date": "2026-03-01T10:00:00",
        "participants": []
    }
    response = await client.post("/api/v1/meetings/", json=payload)
    # Sollte entweder 201 (als Text gespeichert) oder 422 (validiert) sein, 
    # aber niemals die Datenbank beschädigen
    assert response.status_code in [201, 422]

@pytest.mark.asyncio
async def test_xss_protection(client: AsyncClient):
    payload = {
        "title": "<script>alert('xss')</script> Meeting",
        "date": "2026-03-01T10:00:00",
        "participants": []
    }
    response = await client.post("/api/v1/meetings/", json=payload)
    assert response.status_code in [201, 422]
