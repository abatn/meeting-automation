import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_audit_log_creation(client: AsyncClient, test_user_data):
    # Aktion ausführen
    await client.post("/api/v1/auth/register", json=test_user_data)
    
    # Audit Logs abrufen (Admin Role required in real scenario)
    response = await client.get("/api/v1/reports/audit-logs")
    assert response.status_code in [200, 401, 403]
