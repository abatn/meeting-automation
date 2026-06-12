"""
E2E Tests for Tier 2 — Pipeline hardening.

Tier 2.1: Transcription status lifecycle (pending -> completed)
Tier 2.2: pv_sections parsed from Mistral response
Tier 2.3: file_size + duration populated on recording
Tier 2.4: Webhook idempotency (dedup egress_id + event_name)
"""
import asyncio
import time
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.pv import PV, Section
from app.models.recording import Recording
from app.models.transcription import Transcription


# ============================================================================
# Tier 2.4: Webhook Idempotency
# ============================================================================

@pytest.mark.asyncio
async def test_tier24_webhook_idempotency_egress_ended(e2e_client_no_auth: AsyncClient):
    """Sending the same egress_ended webhook twice should be deduplicated."""
    payload = {
        "event": "egress_ended",
        "room_name": "tier24-test-room",
        "egress_id": f"EG_TIER24_{uuid.uuid4().hex[:8]}",
        "file_location": "recordings/tier24/test.ogg",
    }
    headers = {"Authorization": f"Bearer {settings.INTERNAL_API_SECRET}"}

    resp1 = await e2e_client_no_auth.post("/api/v1/livekit/webhooks", json=payload, headers=headers)
    assert resp1.status_code == 200, f"First call failed: {resp1.text}"

    resp2 = await e2e_client_no_auth.post("/api/v1/livekit/webhooks", json=payload, headers=headers)
    assert resp2.status_code == 200, f"Second call failed: {resp2.text}"
    data2 = resp2.json()
    assert data2.get("deduplicated") is True, f"Second call should be deduplicated: {data2}"


@pytest.mark.asyncio
async def test_tier24_webhook_idempotency_egress_failed(e2e_client_no_auth: AsyncClient):
    """Sending the same egress_failed webhook twice should be deduplicated."""
    payload = {
        "event": "egress_failed",
        "room_name": "tier24-test-room-fail",
        "egress_id": f"EG_TIER24_FAIL_{uuid.uuid4().hex[:8]}",
        "egress": {"error": "Test failure"},
    }
    headers = {"Authorization": f"Bearer {settings.INTERNAL_API_SECRET}"}

    resp1 = await e2e_client_no_auth.post("/api/v1/livekit/webhooks", json=payload, headers=headers)
    assert resp1.status_code == 200, f"First call failed: {resp1.text}"

    resp2 = await e2e_client_no_auth.post("/api/v1/livekit/webhooks", json=payload, headers=headers)
    assert resp2.status_code == 200, f"Second call failed: {resp2.text}"
    data2 = resp2.json()
    assert data2.get("deduplicated") is True, f"Second call should be deduplicated: {data2}"


@pytest.mark.asyncio
async def test_tier24_different_egress_ids_not_deduplicated(e2e_client_no_auth: AsyncClient):
    """Two different egress_ids should not be deduplicated against each other."""
    payload1 = {
        "event": "egress_ended",
        "room_name": "tier24-test-room-diff-1",
        "egress_id": f"EG_TIER24_DIFF1_{uuid.uuid4().hex[:8]}",
        "file_location": "recordings/tier24/diff1.ogg",
    }
    payload2 = {**payload1, "egress_id": f"EG_TIER24_DIFF2_{uuid.uuid4().hex[:8]}"}
    headers = {"Authorization": f"Bearer {settings.INTERNAL_API_SECRET}"}

    resp1 = await e2e_client_no_auth.post("/api/v1/livekit/webhooks", json=payload1, headers=headers)
    resp2 = await e2e_client_no_auth.post("/api/v1/livekit/webhooks", json=payload2, headers=headers)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert "deduplicated" not in data2, f"Different egress_id must not be dedup: {data2}"


# ============================================================================
# Tier 2.1 / 2.2 / 2.3: Pipeline-level tests (require real recording + pipeline)
# ============================================================================

@pytest.mark.asyncio
async def test_tier21_22_23_pipeline_completes(
    e2e_client: AsyncClient,
    e2e_meeting: dict,
    db_session: AsyncSession,
    sample_audio_bytes,
    mock_gladia,
    mock_mistral_pv,
    mock_sentinel,
    mock_n8n_transcription,
):
    """End-to-end pipeline test: upload -> pipeline -> verify all Tier 2 fixes.

    Verifies:
    - Tier 2.1: transcription.status == "completed"
    - Tier 2.2: pv_sections persisted (summary, decisions, actions)
    - Tier 2.3: file_size populated from S3 HEAD
    """
    import io
    import wave
    import struct

    meeting_id = e2e_meeting["id"]

    # Upload file directly to S3 (bypass Celery task)
    import boto3
    from app.core.config import settings
    from app.models.recording import Recording
    
    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    
    file_key = f"{e2e_meeting['client_id']}/recordings/{meeting_id}/{uuid.uuid4()}_test.wav"
    s3_client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=file_key,
        Body=sample_audio_bytes,
        ContentType="audio/wav"
    )
    
    # Create recording in DB
    recording_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        recording = Recording(
            id=recording_id,
            client_id=e2e_meeting["client_id"],
            meeting_id=meeting_id,
            file_path=file_key,
            status="uploaded",
            format="audio/wav"
        )
        db.add(recording)
        await db.commit()
    
    expected_file_size = len(sample_audio_bytes)

    from app.tasks.transcription_tasks import _process_recording_pipeline
    rec_for_client = await db_session.execute(
        select(Recording).where(Recording.id == recording_id)
    )
    rec_row = rec_for_client.scalar_one_or_none()
    assert rec_row is not None, "Recording not persisted"
    try:
        await _process_recording_pipeline(recording_id, str(rec_row.client_id))
    except TypeError:
        await _process_recording_pipeline(recording_id)
    except Exception as e:
        pytest.fail(f"Pipeline failed: {e}")

    db_session.expire_all()
    await asyncio.sleep(0.5)

    # Tier 2.3: file_size must be set
    rec_result = await db_session.execute(
        select(Recording).where(Recording.id == recording_id)
    )
    db_rec = rec_result.scalar_one_or_none()
    assert db_rec is not None, "Recording not found"
    assert db_rec.file_size == expected_file_size, (
        f"Tier 2.3: file_size mismatch. Expected {expected_file_size}, got {db_rec.file_size}"
    )
    assert db_rec.duration is not None and db_rec.duration > 0, (
        f"Tier 2.3: duration not populated: {db_rec.duration}"
    )

    # Tier 2.1: transcription status must be "completed"
    trans_result = await db_session.execute(
        select(Transcription).where(Transcription.recording_id == recording_id)
    )
    db_trans = trans_result.scalar_one_or_none()
    assert db_trans is not None, "Transcription not created"
    assert db_trans.status == "completed", (
        f"Tier 2.1: transcription.status should be 'completed', got '{db_trans.status}'"
    )

    # Tier 2.2: pv_sections must be created (at least 1 — summary, decisions, or actions)
    pv_result = await db_session.execute(
        select(PV).where(PV.meeting_id == meeting_id)
    )
    db_pv = pv_result.scalar_one_or_none()
    assert db_pv is not None, "PV not created"

    section_result = await db_session.execute(
        select(Section).where(Section.pv_id == db_pv.id).order_by(Section.order)
    )
    sections = section_result.scalars().all()
    assert len(sections) >= 1, f"Tier 2.2: no pv_sections created. PV={db_pv.id}"

    section_types = {s.type for s in sections if s.type}
    assert "summary" in section_types or "decision" in section_types or "action" in section_types, (
        f"Tier 2.2: no expected section types: {section_types}"
    )

    for s in sections:
        assert s.content is not None and len(s.content) > 0, (
            f"Tier 2.2: section '{s.title}' has empty content"
        )
