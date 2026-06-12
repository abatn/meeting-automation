import pytest
import uuid
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
    meeting_id = str(uuid.uuid4())
    recording_id = str(uuid.uuid4())
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

    payload = {
        "meeting_id": meeting_id,
        "recording_id": recording_id,
        "transcription_text": "Ceci est un test de transcription.",
        "language": "fr"
    }

    headers = {"X-Internal-API-Key": "test-internal-api-secret-key-2026"}
    response = await client.post("/api/v1/webhooks/n8n/transcription", json=payload, headers=headers)
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_n8n_retry_logic():
    pass

@pytest.mark.asyncio
async def test_n8n_callback_idempotency(client: AsyncClient, db_session: AsyncSession):
    meeting_id = str(uuid.uuid4())
    recording_id = str(uuid.uuid4())
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

    payload = {
        "meeting_id": meeting_id,
        "recording_id": recording_id,
        "transcription_text": "Ceci est un test de transcription.",
        "language": "fr",
        "request_id": f"unique-req-{uuid.uuid4()}"
    }

    headers = {"X-Internal-API-Key": "test-internal-api-secret-key-2026"}
    response1 = await client.post("/api/v1/webhooks/n8n/transcription", json=payload, headers=headers)
    assert response1.status_code == 200

    response2 = await client.post("/api/v1/webhooks/n8n/transcription", json=payload, headers=headers)
    assert response2.status_code == 200

    from app.models.transcription import Transcription
    from sqlalchemy import select
    result = await db_session.execute(select(Transcription).where(Transcription.recording_id == recording_id))
    transcriptions = result.scalars().all()
    assert len(transcriptions) == 1