"""
E2E Tests for Phase 78: Sentinel LLM Feature Gate by Subscription Plan.

GRATUIT: skip Sentinel LLM -> faster pipeline, no memory overhead
PRO/ENTREPRISE: full Sentinel summarization -> better PV quality
"""
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.client import Client, SubscriptionPlan
from app.models.meeting import Meeting, MeetingStatus
from app.models.recording import Recording
from app.models.user import User, UserStatus
from app.tasks.transcription_tasks import _process_recording_pipeline


async def _create_client_and_meeting(
    db_session: AsyncSession,
    plan: SubscriptionPlan,
) -> tuple:
    """Helper: create a Client with given plan + a Meeting + return (client, meeting).
    Commits to DB so that separate sessions (used by _upload_and_run_pipeline) can see them."""
    client = Client(
        id=str(uuid.uuid4()),
        company_name=f"Phase78-{plan.value}-{uuid.uuid4().hex[:6]}",
        subscription_plan=plan,
        subscription_status="ACTIVE",
        created_at=datetime.utcnow(),
    )
    db_session.add(client)
    await db_session.flush()

    user = User(
        id=str(uuid.uuid4()),
        email=f"phase78-{plan.value.lower()}-{uuid.uuid4().hex[:6]}@test.com",
        full_name=f"Phase78 {plan.value} User",
        client_id=client.id,
        hashed_password="dummy",
        status=UserStatus.ACTIVE.value,
        created_at=datetime.utcnow(),
    )
    db_session.add(user)
    await db_session.flush()

    meeting = Meeting(
        id=str(uuid.uuid4()),
        client_id=client.id,
        title=f"Phase78 {plan.value} Test Meeting",
        status=MeetingStatus.PLANNED.value,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        creator_id=user.id,
        created_at=datetime.utcnow(),
    )
    db_session.add(meeting)
    await db_session.commit()

    return client, meeting


async def _upload_and_run_pipeline(
    meeting_id: str,
    client_id: str,
    sample_audio_bytes: bytes,
) -> str:
    """Helper: upload audio to S3, create Recording, run pipeline. Returns recording_id."""
    import boto3
    from app.core.config import settings

    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )

    file_key = f"{client_id}/recordings/{meeting_id}/{uuid.uuid4()}_test.wav"
    from app.core.config import get_bucket_name
    bucket = get_bucket_name(client_id)
    try:
        s3_client.create_bucket(Bucket=bucket)
    except Exception:
        pass
    s3_client.put_object(
        Bucket=bucket,
        Key=file_key,
        Body=sample_audio_bytes,
        ContentType="audio/wav",
    )

    recording_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        recording = Recording(
            id=recording_id,
            client_id=client_id,
            meeting_id=meeting_id,
            file_path=file_key,
            status="uploaded",
            format="audio/wav",
        )
        db.add(recording)
        await db.commit()

    await _process_recording_pipeline(recording_id, client_id)
    return recording_id


# ===========================================================================
# Test 1: GRATUIT plan -- Sentinel SKIPPED
# ===========================================================================
@pytest.mark.asyncio
async def test_phase78_gratuit_skips_sentinel(
    db_session: AsyncSession,
    sample_audio_bytes: bytes,
    mock_gladia,
    mock_mistral_pv,
    mock_n8n_transcription,
):
    """GRATUIT plan: pipeline should skip Sentinel LLM and still produce PV."""
    client, meeting = await _create_client_and_meeting(db_session, SubscriptionPlan.GRATUIT)

    mock_service = AsyncMock()
    mock_service.summarize_chunk = AsyncMock(return_value="Should not be called")

    with patch(
        "app.tasks.transcription_tasks.get_sentinel_service",
        return_value=mock_service,
    ):
        recording_id = await _upload_and_run_pipeline(
            str(meeting.id), client.id, sample_audio_bytes,
        )

    # Verify: Sentinel was NOT called
    mock_service.summarize_chunk.assert_not_called()

    # Verify: Recording completed
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Recording).where(Recording.id == recording_id))
        recording = result.scalar_one_or_none()
        assert recording is not None
        assert recording.status == "completed"

    # Verify: Transcription created
    from app.models.transcription import Transcription
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Transcription).where(Transcription.recording_id == recording_id)
        )
        transcription = result.scalar_one_or_none()
        assert transcription is not None
        assert transcription.full_text is not None

    # Verify: PV created
    from app.models.pv import PV
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PV).where(PV.meeting_id == str(meeting.id)))
        pv = result.scalar_one_or_none()
        assert pv is not None


# ===========================================================================
# Test 2: PRO plan -- Sentinel USED
# ===========================================================================
@pytest.mark.asyncio
async def test_phase78_pro_uses_sentinel(
    db_session: AsyncSession,
    sample_audio_bytes: bytes,
    mock_gladia,
    mock_mistral_pv,
    mock_n8n_transcription,
):
    """PRO plan: pipeline should use Sentinel LLM for summarization."""
    client, meeting = await _create_client_and_meeting(db_session, SubscriptionPlan.PRO)

    mock_service = AsyncMock()
    mock_service.summarize_chunk = AsyncMock(
        return_value="Pro summary: This is a summarized chunk from Sentinel."
    )

    with patch(
        "app.tasks.transcription_tasks.get_sentinel_service",
        return_value=mock_service,
    ):
        recording_id = await _upload_and_run_pipeline(
            str(meeting.id), client.id, sample_audio_bytes,
        )

    # Verify: Sentinel WAS called (once per chunk)
    assert mock_service.summarize_chunk.call_count >= 1

    # Verify: Recording completed
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Recording).where(Recording.id == recording_id))
        recording = result.scalar_one_or_none()
        assert recording is not None
        assert recording.status == "completed"

    # Verify: PV created
    from app.models.pv import PV
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PV).where(PV.meeting_id == str(meeting.id)))
        pv = result.scalar_one_or_none()
        assert pv is not None


# ===========================================================================
# Test 3: ENTREPRISE plan -- Sentinel USED
# ===========================================================================
@pytest.mark.asyncio
async def test_phase78_entreprise_uses_sentinel(
    db_session: AsyncSession,
    sample_audio_bytes: bytes,
    mock_gladia,
    mock_mistral_pv,
    mock_n8n_transcription,
):
    """ENTREPRISE plan: pipeline should use Sentinel LLM (same as PRO)."""
    client, meeting = await _create_client_and_meeting(db_session, SubscriptionPlan.ENTREPRISE)

    mock_service = AsyncMock()
    mock_service.summarize_chunk = AsyncMock(
        return_value="Enterprise summary: Premium Sentinel analysis."
    )

    with patch(
        "app.tasks.transcription_tasks.get_sentinel_service",
        return_value=mock_service,
    ):
        recording_id = await _upload_and_run_pipeline(
            str(meeting.id), client.id, sample_audio_bytes,
        )

    # Verify: Sentinel WAS called
    assert mock_service.summarize_chunk.call_count >= 1

    # Verify: Recording completed
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Recording).where(Recording.id == recording_id))
        recording = result.scalar_one_or_none()
        assert recording is not None
        assert recording.status == "completed"


# ===========================================================================
# Test 4: No client found -- fallback to Sentinel (safe default)
# ===========================================================================
@pytest.mark.asyncio
async def test_phase78_unknown_client_uses_sentinel(
    db_session: AsyncSession,
    sample_audio_bytes: bytes,
    mock_gladia,
    mock_mistral_pv,
    mock_n8n_transcription,
):
    """Client with no subscription_plan (nullable): pipeline should fallback to Sentinel."""
    # Create a Client WITHOUT subscription_plan (simulates legacy/free user)
    no_plan_client_id = str(uuid.uuid4())
    meeting_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as db:
        no_plan_client = Client(
            id=no_plan_client_id,
            company_name=f"Phase78-NoPlan-{uuid.uuid4().hex[:6]}",
            subscription_plan=None,  # nullable — no plan set
            subscription_status="ACTIVE",
            created_at=datetime.utcnow(),
        )
        db.add(no_plan_client)
        await db.flush()

        user = User(
            id=str(uuid.uuid4()),
            email=f"phase78-noplan-{uuid.uuid4().hex[:6]}@test.com",
            full_name="Phase78 NoPlan User",
            client_id=no_plan_client_id,
            hashed_password="dummy",
            status=UserStatus.ACTIVE.value,
            created_at=datetime.utcnow(),
        )
        db.add(user)
        await db.flush()

        meeting = Meeting(
            id=meeting_id,
            client_id=no_plan_client_id,
            title="Phase78 NoPlan Meeting",
            status=MeetingStatus.PLANNED.value,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            creator_id=user.id,
            created_at=datetime.utcnow(),
        )
        db.add(meeting)
        await db.commit()

    mock_service = AsyncMock()
    mock_service.summarize_chunk = AsyncMock(
        return_value="Fallback summary for no-plan client."
    )

    with patch(
        "app.tasks.transcription_tasks.get_sentinel_service",
        return_value=mock_service,
    ):
        recording_id = await _upload_and_run_pipeline(
            meeting_id, no_plan_client_id, sample_audio_bytes,
        )

    # Verify: Sentinel WAS called (safe fallback for unknown plan)
    assert mock_service.summarize_chunk.call_count >= 1

    # Verify: Recording completed
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Recording).where(Recording.id == recording_id))
        recording = result.scalar_one_or_none()
        assert recording is not None
        assert recording.status == "completed"
