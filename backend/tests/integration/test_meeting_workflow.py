import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_full_meeting_flow(client: AsyncClient, test_user_data, test_meeting_data):
    # 1. Register/Login
    await client.post("/api/v1/auth/register", json=test_user_data)
    
    # 2. Create Meeting
    m_resp = await client.post("/api/v1/meetings/", json=test_meeting_data)
    assert m_resp.status_code == 201
    meeting_id = m_resp.json()["id"]
    
    # 3. Upload Recording
    r_resp = await client.post(
        f"/api/v1/recordings/upload/{meeting_id}",
        files={"file": ("test.wav", b"content", "audio/wav")}
    )
    assert r_resp.status_code in [201, 202]
    
    # 4. Check Status (Integrated Mock)
    s_resp = await client.get(f"/api/v1/meetings/{meeting_id}")
    assert s_resp.status_code == 200
