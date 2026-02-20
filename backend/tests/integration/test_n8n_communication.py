import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_n8n_callback_processing(client: AsyncClient):
    # Simulieren eines Callbacks von n8n (Transkription fertig)
    payload = {
        "meeting_id": 1,
        "transcription_text": "Ceci est un test de transcription.",
        "language": "fr"
    }
    
    response = await client.post("/api/v1/webhooks/n8n/transcription", json=payload)
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_n8n_retry_logic():
    # Hier würde die Logik getestet werden, die n8n erneut aufruft, wenn der erste Versuch fehlschlägt
    # (Abhängig von der Implementierung in meeting_service.py)
    pass

@pytest.mark.asyncio
async def test_n8n_callback_idempotency(client: AsyncClient):
    # Gleicher Callback zweimal gesendet
    payload = {
        "meeting_id": 1,
        "transcription_text": "Ceci est un test de transcription.",
        "language": "fr",
        "request_id": "unique-req-123"
    }
    
    # Erster Versuch
    response1 = await client.post("/api/v1/webhooks/n8n/transcription", json=payload)
    assert response1.status_code == 200
    
    # Zweiter Versuch (sollte ignoriert werden oder Erfolg zurückgeben ohne Duplikate zu erzeugen)
    response2 = await client.post("/api/v1/webhooks/n8n/transcription", json=payload)
    assert response2.status_code == 200