import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.meeting import Meeting
from app.models.recording import Recording
from app.models.transcription import Transcription
from datetime import datetime

@pytest.mark.asyncio
async def test_n8n_callback_processing(client: AsyncClient, db_session: AsyncSession):
    # Setup: Create a meeting and recording in the test DB
    meeting_id = "test-meeting-id-1"
    recording_id = "test-recording-id-1"
    meeting = Meeting(
        id=meeting_id,
        client_id="test-client-id",
        title="Test Meeting for n8n",
        start_time=datetime.utcnow(),
        creator_id="test-user-id"
    )
    recording = Recording(
        id=recording_id,
        client_id="test-client-id",
        meeting_id=meeting_id,
        file_path="dummy/path.webm",
        status="uploaded"
    )
    db_session.add(meeting)
    db_session.add(recording)
    await db_session.commit()

    # Simulate a callback from n8n (transcription finished)
    payload = {
        "meeting_id": meeting_id,
        "recording_id": recording_id,
        "transcription_text": "Ceci est un test de transcription.",
        "language": "fr"
    }

    # X-Internal-API-Key header is already included in the client fixture headers? Actually we need to add it.
    # The client fixture sets Authorization but not X-Internal-API-Key. So we need to add it.
    headers = {"X-Internal-API-Key": "super-secret-automation-key-2026"}
    response = await client.post("/api/v1/webhooks/n8n/transcription", json=payload, headers=headers)
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_n8n_retry_logic():
    # Hier würde die Logik getestet werden, die n8n erneut aufruft, wenn der erste Versuch fehlschlägt
    # (Abhängig von der Implementierung in meeting_service.py)
    pass

@pytest.mark.asyncio
async def test_n8n_callback_idempotency(client: AsyncClient, db_session: AsyncSession):
    # Setup: Create a meeting and recording
    meeting_id = "test-meeting-id-2"
    recording_id = "test-recording-id-2"
    meeting = Meeting(
        id=meeting_id,
        client_id="test-client-id",
        title="Test Meeting for n8n idempotency",
        start_time=datetime.utcnow(),
        creator_id="test-user-id"
    )
    recording = Recording(
        id=recording_id,
        client_id="test-client-id",
        meeting_id=meeting_id,
        file_path="dummy/path2.webm",
        status="uploaded"
    )
    db_session.add(meeting)
    db_session.add(recording)
    await db_session.commit()

    # Same callback sent twice
    payload = {
        "meeting_id": meeting_id,
        "recording_id": recording_id,
        "transcription_text": "Ceci est un test de transcription.",
        "language": "fr",
        "request_id": "unique-req-123"
    }

    headers = {"X-Internal-API-Key": "super-secret-automation-key-2026"}
    response1 = await client.post("/api/v1/webhooks/n8n/transcription", json=payload, headers=headers)
    assert response1.status_code == 200

    response2 = await client.post("/api/v1/webhooks/n8n/transcription", json=payload, headers=headers)
    assert response2.status_code == 200

    # Verify that only one Transcription exists for the recording
    from app.models.transcription import Transcription
    from sqlalchemy import select
    result = await db_session.execute(select(Transcription).where(Transcription.recording_id == recording_id))
    transcriptions = result.scalars().all()
    assert len(transcriptions) == 1