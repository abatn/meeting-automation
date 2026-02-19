import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient
from backend.app.tasks.celery_app import celery_app
from backend.app.tasks.email_tasks import (
    send_welcome_email, send_meeting_invitation, send_action_reminder,
    send_pv_ready_notification, send_daily_digest, EMAIL_TEMPLATES
)
from backend.app.tasks.transcription_tasks import (
    process_audio_recording, run_whisper_transcription,
    generate_speaker_diarization, detect_code_switching,
    extract_actions_from_transcription
)
from backend.app.tasks.data_retention import (
    cleanup_old_recordings, archive_old_meetings,
    delete_expired_audit_logs, check_overdue_actions
)
from backend.app.models.user import User, UserRole
from backend.app.models.meeting import Meeting, MeetingStatus
from backend.app.models.recording import Recording, RecordingStatus
from backend.app.models.transcription import Transcription, TranscriptionStatus
from backend.app.models.action import Action, ActionStatus
from backend.app.models.pv import PV, PVStatus
from backend.app.models.audit_log import AuditLog
from backend.app.core.config import settings
from backend.app.services.notification_service import notification_service
from backend.app.services.action_service import action_service
from backend.app.services.audit_service import audit_service
from backend.app.services.whisper_client import whisper_client
from backend.app.services.mistral_client import mistral_client
from backend.app.utils.storage import storage_service
import json

# Fixtures for database objects
@pytest.fixture
async def test_user_celery(db_session: AsyncSession) -> User:
    user = User(email="celery_test@example.com", full_name="Celery Test User", hashed_password="hashedpassword", role=UserRole.PARTICIPANT)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture
async def test_admin_user_celery(db_session: AsyncSession) -> User:
    admin_user = User(email="celery_admin@example.com", full_name="Celery Admin User", hashed_password="hashedpassword", role=UserRole.ADMIN)
    db_session.add(admin_user)
    await db_session.commit()
    await db_session.refresh(admin_user)
    return admin_user

@pytest.fixture
async def test_dg_user_celery(db_session: AsyncSession) -> User:
    dg_user = User(email="celery_dg@example.com", full_name="Celery DG User", hashed_password="hashedpassword", role=UserRole.DG)
    db_session.add(dg_user)
    await db_session.commit()
    await db_session.refresh(dg_user)
    return dg_user

@pytest.fixture
async def test_meeting_celery(db_session: AsyncSession, test_user_celery: User) -> Meeting:
    meeting = Meeting(
        title="Celery Test Meeting",
        description="Meeting for Celery tasks",
        date=datetime.now(timezone.utc).date(),
        duration=60,
        organizer_id=test_user_celery.id,
        status=MeetingStatus.PLANNED
    )
    db_session.add(meeting)
    await db_session.commit()
    await db_session.refresh(meeting)
    return meeting

@pytest.fixture
async def test_recording_celery(db_session: AsyncSession, test_meeting_celery: Meeting) -> Recording:
    recording = Recording(
        meeting_id=test_meeting_celery.id,
        file_path="test/path/to/recording.mp3",
        file_size=1024,
        uploaded_at=datetime.now(timezone.utc),
        language="en",
        status=RecordingStatus.UPLOADED
    )
    db_session.add(recording)
    await db_session.commit()
    await db_session.refresh(recording)
    return recording

@pytest.fixture
async def test_transcription_celery(db_session: AsyncSession, test_meeting_celery: Meeting, test_recording_celery: Recording) -> Transcription:
    transcription = Transcription(
        meeting_id=test_meeting_celery.id,
        recording_id=test_recording_celery.id,
        content="This is a test transcription content.",
        language="en",
        status=TranscriptionStatus.COMPLETED
    )
    db_session.add(transcription)
    await db_session.commit()
    await db_session.refresh(transcription)
    return transcription

@pytest.fixture
async def test_action_celery(db_session: AsyncSession, test_user_celery: User, test_meeting_celery: Meeting) -> Action:
    action = Action(
        description="Celery test action",
        due_date=datetime.utcnow() + timedelta(days=7),
        assigned_to=test_user_celery.id,
        meeting_id=test_meeting_celery.id,
        status=ActionStatus.OPEN,
        priority=3
    )
    db_session.add(action)
    await db_session.commit()
    await db_session.refresh(action)
    return action

@pytest.fixture
async def test_pv_celery(db_session: AsyncSession, test_meeting_celery: Meeting, test_user_celery: User) -> PV:
    pv = PV(
        meeting_id=test_meeting_celery.id,
        generated_by_id=test_user_celery.id,
        content="Mock PV Content",
        summary="Mock Summary",
        decisions=["Decision 1"],
        status=PVStatus.DRAFT,
    )
    db_session.add(pv)
    await db_session.commit()
    await db_session.refresh(pv)
    return pv

# Test Celery App
@pytest.mark.asyncio
async def test_celery_health_check(client: AsyncClient):
    result = await celery_app.send_task('backend.app.tasks.celery_app.celery_health_check').get_async()
    assert result == "Celery is healthy!"

# Test Email Tasks
@pytest.mark.asyncio
@patch.object(notification_service, 'send_email', new_callable=AsyncMock)
async def test_send_welcome_email(mock_send_email, test_user_celery: User):
    await send_welcome_email.delay(test_user_celery.id)
    mock_send_email.assert_called_once_with(
        test_user_celery.email,
        EMAIL_TEMPLATES["welcome"]["subject"],
        EMAIL_TEMPLATES["welcome"]["body"].format(user_name=test_user_celery.full_name)
    )

@pytest.mark.asyncio
@patch.object(notification_service, 'send_email', new_callable=AsyncMock)
async def test_send_meeting_invitation(mock_send_email, test_user_celery: User, test_meeting_celery: Meeting):
    await send_meeting_invitation.delay(test_meeting_celery.id, [test_user_celery.id])
    mock_send_email.assert_called_once()
    args, kwargs = mock_send_email.call_args
    assert args[0] == test_user_celery.email
    assert test_meeting_celery.title in args[1] # Subject
    assert test_meeting_celery.title in args[2] # Body

@pytest.mark.asyncio
@patch.object(notification_service, 'send_email', new_callable=AsyncMock)
async def test_send_action_reminder(mock_send_email, test_action_celery: Action):
    await send_action_reminder.delay(test_action_celery.id)
    mock_send_email.assert_called_once()
    args, kwargs = mock_send_email.call_args
    assert args[0] == test_action_celery.assignee.email
    assert test_action_celery.description in args[1] # Subject
    assert test_action_celery.description in args[2] # Body

@pytest.mark.asyncio
@patch.object(notification_service, 'send_email', new_callable=AsyncMock)
async def test_send_pv_ready_notification(mock_send_email, test_pv_celery: PV, test_user_celery: User):
    await send_pv_ready_notification.delay(test_pv_celery.id, [test_user_celery.id])
    mock_send_email.assert_called_once()
    args, kwargs = mock_send_email.call_args
    assert args[0] == test_user_celery.email
    assert test_pv_celery.meeting.title in args[1] # Subject
    assert test_pv_celery.meeting.title in args[2] # Body

@pytest.mark.asyncio
@patch.object(notification_service, 'send_email', new_callable=AsyncMock)
@patch.object(action_service, 'get_actions_by_user', new_callable=AsyncMock)
async def test_send_daily_digest(mock_get_actions_by_user, mock_send_email, test_user_celery: User):
    mock_get_actions_by_user.side_effect = [[test_action_celery], []] # One overdue, no upcoming
    await send_daily_digest.delay()
    mock_send_email.assert_called_once()
    args, kwargs = mock_send_email.call_args
    assert args[0] == test_user_celery.email
    assert "täglicher Meeting Automation Digest" in args[1] # Subject
    assert test_action_celery.description in args[2] # Body (overdue actions)

# Test Transcription Tasks
@pytest.mark.asyncio
@patch("backend.app.tasks.transcription_tasks.run_whisper_transcription.delay", new_callable=AsyncMock)
@patch("backend.app.tasks.transcription_tasks.generate_speaker_diarization.delay", new_callable=AsyncMock)
@patch("backend.app.tasks.transcription_tasks.detect_code_switching.delay", new_callable=AsyncMock)
@patch("backend.app.tasks.transcription_tasks.extract_actions_from_transcription.delay", new_callable=AsyncMock)
@patch("backend.app.utils.storage.get_file_path", return_value="/mock/audio/path.mp3")
@patch.object(notification_service, 'send_error_notification', new_callable=AsyncMock)
async def test_process_audio_recording(
    mock_send_error_notification,
    mock_get_file_path,
    mock_extract_actions,
    mock_detect_code_switching,
    mock_generate_diarization,
    mock_run_whisper,
    db_session: AsyncSession,
    test_recording_celery: Recording
):
    mock_run_whisper.return_value = "Mocked transcription content."
    settings.ENABLE_SPEAKER_DIARIZATION = True
    settings.ENABLE_CODE_SWITCHING_DETECTION = True

    await process_audio_recording.delay(test_recording_celery.id)

    mock_get_file_path.assert_called_once_with(test_recording_celery.file_path)
    mock_run_whisper.assert_called_once_with("/mock/audio/path.mp3", test_recording_celery.language)
    mock_generate_diarization.assert_called_once()
    mock_detect_code_switching.assert_called_once()
    mock_extract_actions.assert_called_once()

    await db_session.refresh(test_recording_celery)
    assert test_recording_celery.status == RecordingStatus.TRANSCRIBED
    mock_send_error_notification.assert_not_called()

@pytest.mark.asyncio
@patch.object(whisper_client, 'transcribe_audio', new_callable=AsyncMock)
async def test_run_whisper_transcription(mock_transcribe_audio):
    mock_transcribe_audio.return_value = "Whisper output."
    result = await run_whisper_transcription.delay("/fake/path.mp3", "en")
    assert result == "Whisper output."
    mock_transcribe_audio.assert_called_once_with("/fake/path.mp3", "en")

@pytest.mark.asyncio
async def test_generate_speaker_diarization(db_session: AsyncSession, test_transcription_celery: Transcription):
    await generate_speaker_diarization.delay(test_transcription_celery.id)
    await db_session.refresh(test_transcription_celery)
    assert test_transcription_celery.speaker_diarization is not None
    diarization_data = json.loads(test_transcription_celery.speaker_diarization)
    assert "speakers" in diarization_data

@pytest.mark.asyncio
async def test_detect_code_switching(db_session: AsyncSession, test_transcription_celery: Transcription):
    await detect_code_switching.delay(test_transcription_celery.id)
    await db_session.refresh(test_transcription_celery)
    assert test_transcription_celery.code_switching_detection is not None
    code_switching_data = json.loads(test_transcription_celery.code_switching_detection)
    assert "detected" in code_switching_data

@pytest.mark.asyncio
@patch.object(mistral_client, 'extract_action_points', new_callable=AsyncMock)
async def test_extract_actions_from_transcription(mock_extract_action_points, db_session: AsyncSession, test_transcription_celery: Transcription):
    mock_extract_action_points.return_value = json.dumps(["Action 1", "Action 2"])
    await extract_actions_from_transcription.delay(test_transcription_celery.id)
    await db_session.refresh(test_transcription_celery)
    assert test_transcription_celery.actions_extracted is True
    mock_extract_action_points.assert_called_once_with(test_transcription_celery.content)

# Test Data Retention Tasks
@pytest.mark.asyncio
@patch.object(storage_service, 'delete_from_s3', new_callable=AsyncMock)
@patch.object(audit_service, 'create_audit_log', new_callable=AsyncMock)
async def test_cleanup_old_recordings(mock_create_audit_log, mock_delete_from_s3, db_session: AsyncSession, test_recording_celery: Recording):
    settings.RECORDING_RETENTION_DAYS = 0 # Make it immediately old
    test_recording_celery.uploaded_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.commit()
    await db_session.refresh(test_recording_celery)

    await cleanup_old_recordings.delay()

    mock_delete_from_s3.assert_called_once_with(test_recording_celery.file_path)
    mock_create_audit_log.assert_called_once()
    
    # Verify recording is deleted from DB
    deleted_recording = await db_session.get(Recording, test_recording_celery.id)
    assert deleted_recording is None

@pytest.mark.asyncio
@patch.object(audit_service, 'create_audit_log', new_callable=AsyncMock)
async def test_archive_old_meetings(mock_create_audit_log, db_session: AsyncSession, test_meeting_celery: Meeting, test_transcription_celery: Transcription, test_pv_celery: PV):
    settings.MEETING_ARCHIVE_DAYS = 0 # Make it immediately old
    test_meeting_celery.end_time = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.commit()
    await db_session.refresh(test_meeting_celery)

    await archive_old_meetings.delay()

    mock_create_audit_log.assert_called_once()
    
    await db_session.refresh(test_meeting_celery)
    assert test_meeting_celery.status == MeetingStatus.ARCHIVED

    await db_session.refresh(test_transcription_celery)
    assert test_transcription_celery.status == TranscriptionStatus.ARCHIVED

    await db_session.refresh(test_pv_celery)
    assert test_pv_celery.status == PVStatus.ARCHIVED

@pytest.mark.asyncio
async def test_delete_expired_audit_logs(db_session: AsyncSession, test_admin_user_celery: User):
    settings.AUDIT_LOG_RETENTION_DAYS = 0 # Make it immediately old
    old_audit_log = AuditLog(
        user_id=test_admin_user_celery.id,
        event_type="TEST_EVENT",
        resource_type="User",
        resource_id=test_admin_user_celery.id,
        details="Old log entry",
        timestamp=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db_session.add(old_audit_log)
    await db_session.commit()
    await db_session.refresh(old_audit_log)

    await delete_expired_audit_logs.delay()

    deleted_log = await db_session.get(AuditLog, old_audit_log.id)
    assert deleted_log is None

@pytest.mark.asyncio
@patch.object(notification_service, 'send_action_overdue_notification', new_callable=AsyncMock)
async def test_check_overdue_actions(mock_send_notification, db_session: AsyncSession, test_action_celery: Action):
    test_action_celery.due_date = datetime.now(timezone.utc) - timedelta(days=1)
    test_action_celery.status = ActionStatus.OPEN
    await db_session.commit()
    await db_session.refresh(test_action_celery)

    await check_overdue_actions.delay()

    await db_session.refresh(test_action_celery)
    assert test_action_celery.status == ActionStatus.OVERDUE
    mock_send_notification.assert_called_once()

# Test Retry Logic (example for one task)
@pytest.mark.asyncio
@patch.object(notification_service, 'send_email', side_effect=Exception("Simulated email error"))
async def test_send_welcome_email_retry_logic(mock_send_email, test_user_celery: User):
    with pytest.raises(Exception, match="Simulated email error"):
        await send_welcome_email.delay(test_user_celery.id)
    assert mock_send_email.call_count == settings.CELERY_TASK_MAX_RETRIES + 1 # Initial call + retries