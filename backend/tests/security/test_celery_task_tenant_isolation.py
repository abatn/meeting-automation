"""
E2E Security Test: Celery Task Tenant Isolation Vulnerability (Punkt #4)

Verifies that Celery tasks in transcription_tasks.py validate client_id
before processing recordings (Defense-in-Depth).

Vulnerability:
- _process_recording_pipeline (line 109): select(Recording).where(Recording.id == recording_id)
  WITHOUT client_id filter — any recording can be processed if task is invoked directly
- Same issue in exception handler (line 166)
- API layer (transcriptions.py:29) checks client_id, but task itself does not

Test Strategy:
- Create two tenants with recordings
- Call _process_recording_pipeline directly (simulating direct task invocation)
- Mock external services (Gladia, S3, Mistral) to isolate DB-level behavior
- Verify that the pipeline processes a recording regardless of tenant
  (confirming the vulnerability: no client_id check in the task)
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.user import User, UserStatus, Role
from app.models.client import Client, SubscriptionStatus
from app.models.meeting import Meeting
from app.models.recording import Recording
from app.models.pv import PV
from app.models.transcription import Transcription
from app.core.database import AsyncSessionLocal
from app.tasks.transcription_tasks import _process_recording_pipeline


TENANT_A_CLIENT_ID = "celery-tenant-a-id"
TENANT_B_CLIENT_ID = "celery-tenant-b-id"
TENANT_A_USER_ID = "celery-tenant-a-user-id"
TENANT_B_USER_ID = "celery-tenant-b-user-id"


async def setup_two_tenants(db_session: AsyncSession):
    roles = await db_session.execute(select(Role))
    existing_roles = {r.name: r for r in roles.scalars().all()}
    dg_role = existing_roles.get("dg")

    for client_id, company in [
        (TENANT_A_CLIENT_ID, "Celery Tenant A Corp"),
        (TENANT_B_CLIENT_ID, "Celery Tenant B Corp"),
    ]:
        existing = await db_session.execute(select(Client).where(Client.id == client_id))
        if not existing.scalar_one_or_none():
            db_session.add(Client(
                id=client_id,
                company_name=company,
                subscription_status=SubscriptionStatus.ACTIVE,
            ))

    for user_id, email, client_id in [
        (TENANT_A_USER_ID, "celery-a@example.com", TENANT_A_CLIENT_ID),
        (TENANT_B_USER_ID, "celery-b@example.com", TENANT_B_CLIENT_ID),
    ]:
        existing = await db_session.execute(select(User).where(User.id == user_id))
        if not existing.scalar_one_or_none():
            db_session.add(User(
                id=user_id,
                client_id=client_id,
                email=email,
                hashed_password=get_password_hash("TestPassword123!"),
                status=UserStatus.ACTIVE.value,
                is_superuser=False,
                roles=[dg_role] if dg_role else [],
            ))

    await db_session.commit()


async def create_recording_for_tenant(
    db_session: AsyncSession,
    client_id: str,
    user_id: str,
) -> str:
    meeting_id = str(uuid.uuid4())
    recording_id = str(uuid.uuid4())

    meeting = Meeting(
        id=meeting_id,
        client_id=client_id,
        title=f"Meeting for {client_id[:8]}",
        start_time=datetime(2026, 3, 1, 10, 0, 0),
        end_time=datetime(2026, 3, 1, 11, 0, 0),
        location="Virtual",
        creator_id=user_id,
    )
    db_session.add(meeting)
    await db_session.flush()

    recording = Recording(
        id=recording_id,
        client_id=client_id,
        meeting_id=meeting_id,
        file_path=f"recordings/{recording_id}.wav",
        status="uploaded",
    )
    db_session.add(recording)
    await db_session.commit()

    return recording_id


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Known vulnerability: celery task lacks client_id filter - tracked for fix")
async def test_celery_task_no_client_id_filter_vulnerability(db_session: AsyncSession):
    """
    VULNERABILITY CONFIRMATION: _process_recording_pipeline queries Recording
    by ID only (line 109), WITHOUT filtering by client_id.

    This test directly invokes the pipeline function for a recording belonging
    to Tenant B, proving that the task does not enforce tenant isolation.
    If the task had client_id validation, it would reject cross-tenant access.
    """
    await setup_two_tenants(db_session)
    recording_b_id = await create_recording_for_tenant(
        db_session, TENANT_B_CLIENT_ID, TENANT_B_USER_ID
    )

    mock_gladia_result = {
        "full_text": "Confidential Tenant B discussion about strategy.",
        "segments": [
            {"speaker": "Speaker 1", "start": 0.0, "end": 5.0, "text": "Confidential Tenant B discussion"},
        ],
    }
    mock_pv_data = {
        "title": "Tenant B PV",
        "tags": "confidential",
        "summary": "Confidential summary",
        "decisions": ["Decision 1"],
        "actions": [],
    }

    with patch(
        "app.tasks.transcription_tasks.AsyncSessionLocal",
        return_value=db_session,
    ), patch(
        "app.tasks.transcription_tasks._download_audio",
        new_callable=AsyncMock,
        return_value="/tmp/fake_audio.wav",
    ), patch(
        "app.tasks.transcription_tasks.gladia_service"
    ) as mock_gladia, patch(
        "app.tasks.transcription_tasks.PVService.generate_pv",
        new_callable=AsyncMock,
        return_value=mock_pv_data,
    ), patch(
        "app.tasks.transcription_tasks.sentinel"
    ) as mock_sentinel, patch(
        "app.tasks.transcription_tasks.publish_status"
    ), patch(
        "app.tasks.transcription_tasks._notify_n8n_completion",
        new_callable=AsyncMock,
    ), patch(
        "app.tasks.transcription_tasks._record_minutes_usage",
        new_callable=AsyncMock,
    ):
        mock_gladia.transcribe_and_diarize = AsyncMock(return_value=mock_gladia_result)
        mock_sentinel.summarize_chunk = AsyncMock(return_value="Summary chunk")

        try:
            await _process_recording_pipeline(recording_b_id)
        except Exception:
            pass

    # Verify: The task processed Tenant B's recording without any client_id check
    # If the task had client_id validation, it would have rejected this or failed
    await db_session.refresh(await db_session.get(Recording, recording_b_id))
    result = await db_session.execute(
        select(Recording).where(Recording.id == recording_b_id)
    )
    recording = result.scalar_one_or_none()

    assert recording is not None, "Recording should exist"

    if recording.status == "completed":
        # VULNERABILITY CONFIRMED: Task processed another tenant's recording
        # Check that transcription was created (proves full pipeline ran)
        trans_result = await db_session.execute(
            select(Transcription).where(Transcription.recording_id == recording_b_id)
        )
        transcription = trans_result.scalar_one_or_none()

        if transcription is not None:
            pytest.fail(
                f"VULNERABILITY CONFIRMED: Celery task processed Tenant B's recording "
                f"without client_id validation! Recording status: {recording.status}, "
                f"Transcription created: {transcription.id}, "
                f"client_id on transcription: {transcription.client_id}"
            )

    # Even if the pipeline failed due to mocked services,
    # the fact that it queried and modified the recording (status change)
    # without client_id check proves the vulnerability
    if recording.status in ("transcribing", "failed"):
        # The task AT LEAST changed the recording status from "uploaded"
        # This proves it accessed the recording without checking client_id
        result2 = await db_session.execute(
            select(Recording).where(
                Recording.id == recording_b_id,
                Recording.client_id == TENANT_A_CLIENT_ID,
            )
        )
        cross_tenant_rec = result2.scalar_one_or_none()

        if cross_tenant_rec is None and recording.status != "uploaded":
            pytest.fail(
                f"VULNERABILITY CONFIRMED: Celery task accessed and modified "
                f"Tenant B's recording (status={recording.status}) without "
                f"client_id validation. The query at line 109 uses only "
                f"Recording.id, not Recording.client_id."
            )


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Known vulnerability: exception handler lacks client_id filter - tracked for fix")
async def test_celery_task_exception_handler_no_client_id(db_session: AsyncSession):
    """
    VULNERABILITY: Exception handler at line 166 also queries Recording
    without client_id filter. A failed task can modify any tenant's
    recording status to "failed".
    """
    await setup_two_tenants(db_session)
    recording_b_id = await create_recording_for_tenant(
        db_session, TENANT_B_CLIENT_ID, TENANT_B_USER_ID
    )

    with patch(
        "app.tasks.transcription_tasks._download_audio",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.tasks.transcription_tasks.publish_status"
    ):
        try:
            await _process_recording_pipeline(recording_b_id)
        except Exception:
            pass

    # Verify: Exception handler set status to "failed" without client_id check
    async with AsyncSessionLocal() as verify_session:
        result = await verify_session.execute(
            select(Recording).where(Recording.id == recording_b_id)
        )
        recording = result.scalar_one_or_none()

        assert recording is not None

        if recording.status == "failed":
            # VULNERABILITY CONFIRMED: Exception handler at line 166-170
            # modified Tenant B's recording status without client_id validation
            pytest.fail(
                f"VULNERABILITY CONFIRMED: Exception handler (line 166) set "
                f"Tenant B's recording to 'failed' without client_id check. "
                f"Query: select(Recording).where(Recording.id == recording_id) "
                f"— missing .where(Recording.client_id == expected_client_id)"
            )


@pytest.mark.asyncio
async def test_api_initiate_transcription_enforces_client_id(
    client, db_session: AsyncSession
):
    """
    POSITIVE CONTROL: API endpoint /transcriptions/initiate DOES check client_id.
    This confirms the API layer is secure, but the task layer is not.
    """
    await setup_two_tenants(db_session)
    recording_b_id = await create_recording_for_tenant(
        db_session, TENANT_B_CLIENT_ID, TENANT_B_USER_ID
    )

    from jose import jwt
    from app.core.config import settings

    token_a = jwt.encode(
        {"sub": TENANT_A_USER_ID, "client_id": TENANT_A_CLIENT_ID},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}

    response = await client.post(
        "/api/v1/transcriptions/initiate",
        json={"recording_id": recording_b_id},
        headers=headers_a,
    )

    assert response.status_code == 404, (
        f"API should block cross-tenant transcription initiation. "
        f"Got: {response.status_code}, Body: {response.text}"
    )


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Known vulnerability: direct task invocation bypasses API tenant isolation - tracked for fix")
async def test_celery_task_direct_invocation_bypasses_api_protection(
    db_session: AsyncSession,
):
    """
    PROOF OF CONCEPT: While the API blocks cross-tenant access,
    directly invoking the Celery task bypasses this protection entirely.

    This simulates: compromised worker, queue manipulation, or internal
    code path that calls process_recording.delay() without proper auth.
    """
    await setup_two_tenants(db_session)
    recording_b_id = await create_recording_for_tenant(
        db_session, TENANT_B_CLIENT_ID, TENANT_B_USER_ID
    )

    from app.tasks.transcription_tasks import process_recording

    # Direct task invocation (simulating queue manipulation)
    # In eager mode, this runs synchronously
    with patch(
        "app.tasks.transcription_tasks._download_audio",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.tasks.transcription_tasks.publish_status"
    ):
        try:
            process_recording(recording_b_id)
        except Exception:
            pass

    # Verify the task attempted to process the recording
    async with AsyncSessionLocal() as verify_session:
        result = await verify_session.execute(
            select(Recording).where(Recording.id == recording_b_id)
        )
        recording = result.scalar_one_or_none()

        assert recording is not None

        if recording.status != "uploaded":
            pytest.fail(
                f"VULNERABILITY CONFIRMED: Direct Celery task invocation "
                f"processed Tenant B's recording without client_id check. "
                f"Status changed from 'uploaded' to '{recording.status}'. "
                f"Defense-in-Depth VIOLATION: Task should validate client_id "
                f"independently of API layer."
            )
