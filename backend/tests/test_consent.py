import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_consent_status_returns_defaults(client: AsyncClient):
    response = await client.get("/api/v1/consent/status", headers={"X-Client-ID": "test-client-id"})
    assert response.status_code == 200
    data = response.json()
    assert data["audio_recording"] is False
    assert data["voice_profiling"] is False
    assert data["third_party_sharing"] is False
    assert data["transcript_storage"] is False


@pytest.mark.asyncio
async def test_grant_consent(client: AsyncClient):
    consents = [
        {"consent_type": "audio_recording", "consented": True},
        {"consent_type": "third_party_sharing", "consented": True},
    ]
    response = await client.post("/api/v1/consent/grant", json=consents, headers={"X-Client-ID": "test-client-id"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["consented"] is True
    assert data[0]["consent_type"] == "audio_recording"


@pytest.mark.asyncio
async def test_withdraw_consent(client: AsyncClient):
    consents = [{"consent_type": "voice_profiling", "consented": True}]
    await client.post("/api/v1/consent/grant", json=consents, headers={"X-Client-ID": "test-client-id"})

    response = await client.post(
        "/api/v1/consent/withdraw",
        params={"consent_type": "voice_profiling"},
        headers={"X-Client-ID": "test-client-id"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["consented"] is False
    assert data["withdrawn_at"] is not None


@pytest.mark.asyncio
async def test_consent_history(client: AsyncClient):
    consents = [{"consent_type": "audio_recording", "consented": True}]
    await client.post("/api/v1/consent/grant", json=consents, headers={"X-Client-ID": "test-client-id"})

    response = await client.get("/api/v1/consent/history", headers={"X-Client-ID": "test-client-id"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
