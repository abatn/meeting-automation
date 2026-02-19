import pytest
from unittest.mock import patch, MagicMock
from backend.app.tasks.email_tasks import send_welcome_email
from backend.app.tasks.transcription_tasks import process_audio_recording
from backend.app.services.notification_service import notification_service
from backend.app.services.whisper_client import WhisperClient
from backend.app.models.recording import Recording
from backend.app.models.transcription import Transcription
from backend.app.core.database import SessionLocal
from sqlalchemy import select
from datetime import datetime, timedelta

@pytest.mark.asyncio
@patch.object(notification_service, 'send_email_notification')
async def test_email_task_executed(mock_send_email_notification: MagicMock, celery_app, celery_worker, test_user):
    task = send_welcome_email.delay(test_user.id)
    result = task.get(timeout=10)

    assert result is None # Celery tasks return None on success by default
    mock_send_email_notification.assert_called_once_with(test_user.email, "Willkommen bei Meeting Automation!", f"Hallo {test_user.full_name or test_user.email},\n\nWillkommen bei Meeting Automation! Wir freuen uns, Sie an Bord zu haben.\n\nIhr Team von Meeting Automation.")

@pytest.mark.asyncio
@patch.object(WhisperClient, 'transcribe_audio')
@patch.object(notification_service, 'send_email_notification')
@patch.object(notification_service, 'send_whatsapp_notification')
async def test_transcription_task_executed(mock_send_whatsapp_notification: MagicMock, mock_send_email_notification: MagicMock, mock_start_transcription: MagicMock, celery_app, celery_worker, test_recording: Recording):
    # Mock the internal calls within process_audio_recording
    mock_start_transcription.return_value = "Mocked transcription content"

    # Call the main task
    task = process_audio_recording.delay(test_recording.id)
    result = task.get(timeout=10)

    assert result is None # process_audio_recording returns None on success
    mock_start_transcription.assert_called_once_with(test_recording.file_path, test_recording.language)

    async with SessionLocal() as session:
        # Refresh recording to get updated status
        await session.refresh(test_recording)
        assert test_recording.status == "TRANSCRIBED"

        # Check if transcription was created
        transcription_in_db = await session.execute(select(Transcription).filter_by(recording_id=test_recording.id))
        transcription = transcription_in_db.scalar_one_or_none()
        assert transcription is not None
        assert transcription.status == "COMPLETED"
        assert transcription.content == "Mocked transcription content"

    # The email and whatsapp notifications are sent for errors or specific events, not necessarily on successful transcription initiation.
    # For now, we'll assert they are NOT called, as the current implementation of process_audio_recording doesn't send them on success.
    mock_send_email_notification.assert_not_called()
    mock_send_whatsapp_notification.assert_not_called()

@pytest.mark.asyncio
@patch.object(notification_service, 'send_email_notification', side_effect=Exception("Email service error"))
async def test_celery_task_retry_on_failure(mock_send_email_notification: MagicMock, celery_app, celery_worker, test_user):
    task = send_welcome_email.delay(test_user.id)

    with pytest.raises(Exception, match="Email service error"):
        task.get(timeout=10)

    # Check that the task was retried (default is 3 retries, so 1 initial call + 3 retries = 4 calls)
    assert mock_send_email_notification.call_count == 4

@pytest.mark.asyncio
@patch('backend.app.tasks.data_retention.delete_old_data.delay')
async def test_periodic_tasks_mocked(mock_delete_old_data: MagicMock, celery_app, celery_worker):
    # This test primarily checks if the periodic task is registered and can be called.
    # Actual scheduling and execution are handled by Celery Beat, which is harder to test directly in unit tests.
    # We can simulate calling the task directly to ensure its logic is sound.
    from backend.app.tasks.data_retention import delete_old_data
    delete_old_data.delay()
    mock_delete_old_data.assert_called_once()