"""
E2E Tests for Recording-Transcription Pipeline.

Covers the full end-to-end flow:
1. Create meeting
2. Upload recording
3. Trigger Celery task (eager mode in E2E)
4. Gladia transcription (mocked)
5. Sentinel summarization (real, local)
6. PV generation (mocked)
7. Action extraction (real)
8. n8n notification (mocked)
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.e2e.conftest import (
    e2e_client,
    e2e_meeting,
    e2e_recording,
    e2e_transcription,
    e2e_pv,
    mock_gladia,
    mock_mistral_pv,
    mock_n8n_transcription,
)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_full_recording_transcription_pipeline(
    e2e_meeting: dict,
    e2e_recording: dict,
    e2e_transcription: dict,
    e2e_pv: dict,
):
    """
    E2E: Full pipeline from recording upload to transcription and PV generation.
    Verifies that:
    - Recording is uploaded successfully
    - Transcription is created with mocked Gladia data
    - PV is generated with mocked Mistral data
    """
    # e2e_recording fixture triggers upload; e2e_transcription waits for transcription;
    # e2e_pv waits for PV. If any step fails, fixtures will raise.

    # Verify recording state
    recording = e2e_recording
    assert recording["status"] in ["uploaded", "completed", "transcribing", "analyzing"]
    assert recording["meeting_id"] == e2e_meeting["id"]

    # Verify transcription
    transcription = e2e_transcription
    assert transcription["recording_id"] == recording["id"]
    assert transcription["meeting_id"] == e2e_meeting["id"]
    assert "full_text" in transcription
    assert len(transcription["full_text"]) > 0
    # Transcription should contain the mocked Gladia text
    assert "Speaker 1" in transcription["full_text"] or "test transcription" in transcription["full_text"].lower()
    assert "Speaker 2" in transcription["full_text"] or "welcome" in transcription["full_text"].lower()

    # Verify PV
    pv = e2e_pv
    assert pv["meeting_id"] == e2e_meeting["id"]
    assert pv["title"] == "E2E Test Meeting PV"
    assert "automation" in pv["tags"].lower()
    # Content includes summary section (French "Résumé" or English "Summary")
    pv_html_lower = pv["content_html"].lower()
    assert "résumé" in pv_html_lower or "summary" in pv_html_lower
    # Also check that the expected summary text is present
    assert "e2e test infrastructure" in pv_html_lower

    # Verify that the transcription segments were preserved
    assert isinstance(transcription["segments"], list)
    if transcription["segments"]:
        assert any("speaker" in seg or "Speaker" in str(seg) for seg in transcription["segments"])


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_recording_upload_success(
    e2e_client,
    e2e_meeting: dict,
    mock_gladia,
    mock_mistral_pv,
    mock_n8n_transcription
):
    """
    E2E: Uploading a recording returns success and triggers background processing.
    """
    meeting_id = e2e_meeting["id"]
    audio_bytes = b"TEST_AUDIO_CONTENT"
    files = {"file": ("upload_test.wav", audio_bytes, "audio/wav")}
    resp = await e2e_client.post(f"/api/v1/recordings/upload/{meeting_id}", files=files)
    assert resp.status_code in [200, 201, 202]
    recording = resp.json()
    assert "id" in recording
    assert recording["meeting_id"] == meeting_id


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_transcription_uses_mocked_gladia(
    e2e_transcription: dict,
    mock_gladia
):
    """
    E2E: Verify that the transcription content matches the mocked Gladia output.
    The mock is injected via fixtures; we assert the expected text appears.
    """
    transcription = e2e_transcription
    full_text = transcription["full_text"].lower()
    assert "test transcription" in full_text or "speaker" in full_text
    # Check segments
    segments = transcription["segments"]
    assert len(segments) >= 1
    # The mock expects two segments with speakers
    speakers = [seg.get("speaker", "") for seg in segments]
    assert any("Speaker 1" in s for s in speakers)
    assert any("Speaker 2" in s for s in speakers)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_pv_generated_from_transcription(
    e2e_pv: dict,
    mock_mistral_pv
):
    """
    E2E: Verify that PV content matches the mocked Mistral output.
    """
    pv = e2e_pv
    assert pv["title"] == "E2E Test Meeting PV"
    assert "automation" in pv["tags"].lower()
    assert "e2e" in pv["tags"].lower()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_actions_extracted_from_pv(
    e2e_pv: dict,
    db_session: AsyncSession
):
    """
    E2E: Verify that actions were extracted from PV and stored in the database.
    """
    from app.models.action import Action as ActionModel
    meeting_id = e2e_pv["meeting_id"]

    db_session.expire_all()  # pipeline used a separate session; force fresh read
    result = await db_session.execute(
        select(ActionModel).where(ActionModel.meeting_id == meeting_id)
    )
    actions = result.scalars().all()

    # The mock PV data had 2 actions. We should have at least one.
    assert len(actions) >= 1
    # Check that at least one action has a description matching our mock
    descriptions = [a.title for a in actions]
    assert any("E2E" in desc or "Mock" in desc for desc in descriptions)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_n8n_webhook_notified_on_completion(
    e2e_recording: dict,
    mock_n8n_transcription
):
    """
    E2E: Verify that n8n webhook is called (mocked) after transcription pipeline completes.
    The mock will be called if _notify_n8n_completion is invoked.
    """
    # e2e_recording triggers pipeline; mock_n8n_transcription should have been called.
    assert mock_n8n_transcription.called or mock_n8n_transcription.await_count >= 1
    # Verify call arguments: should be (recording_id, meeting_id)
    args = mock_n8n_transcription.call_args[0] if mock_n8n_transcription.call_args else ()
    if args:
        recording_id_arg, meeting_id_arg = args[0], args[1]
        assert recording_id_arg == e2e_recording["id"]
        assert meeting_id_arg == e2e_recording["meeting_id"]
