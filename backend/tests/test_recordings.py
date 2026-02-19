import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.recording import Recording
from backend.app.models.meeting import Meeting
from backend.app.schemas.recording import RecordingCreate, RecordingUpdate
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from http import HTTPStatus
from backend.app.models.user import User # Import User model
from backend.app.models.transcription import Transcription # Import Transcription model
from backend.app.api import deps # Import deps to get current_user
from io import BytesIO # Import BytesIO

@pytest.mark.asyncio
async def test_create_recording(client: AsyncClient, auth_headers: dict, test_meeting: Meeting, mock_whisper: AsyncMock, db_session: AsyncSession, test_user: User):
    # Simulate an audio file upload
    file_content = b"This is a dummy audio file content."
    file = {"file": ("test_recording.mp3", BytesIO(file_content), "audio/mpeg")}

    # Mock S3 upload and metadata extraction
    with patch("backend.app.utils.storage.storage_service.upload_to_s3", new_callable=AsyncMock) as mock_s3_upload, \
         patch("backend.app.services.recording_service.extract_audio_metadata", new_callable=AsyncMock) as mock_extract_metadata:
        
        mock_s3_upload.return_value = True
        mock_extract_metadata.return_value = 120.0 # Mock duration
        
        response = await client.post(
            f"/api/v1/recordings/upload?meeting_id={test_meeting.id}",
            files=file,
            headers=auth_headers
        )
        assert response.status_code == HTTPStatus.CREATED
        data = response.json()
        assert "id" in data
        assert "status" in data
        assert data["status"] == "completed"
        assert "message" in data
        assert "Recording upload initiated successfully." in data["message"]
        
        # Verify S3 upload was called
        mock_s3_upload.assert_called_once()

        # Verify recording in database
        recording_in_db = await db_session.execute(select(Recording).filter_by(id=data["id"]))
        recording = recording_in_db.scalar_one_or_none()
        assert recording is not None
        assert recording.meeting_id == test_meeting.id
        assert recording.uploader_id == test_user.id
        assert recording.status == "completed"
        assert recording.file_size == len(file_content)
        # The file path is generated with UUID, so we check if it starts with "recordings/1/"
        assert recording.file_path.startswith(f"recordings/{test_meeting.id}/")
        assert recording.file_path.endswith(".mp3")

@pytest.mark.asyncio
async def test_list_recordings(client: AsyncClient, auth_headers: dict, test_recording: Recording, test_meeting: Meeting, db_session: AsyncSession, test_user: User):
    # Create another recording for filtering
    another_recording = Recording(
        meeting_id=test_meeting.id,
        uploader_id=test_user.id, # Add uploader_id
        file_path="another/path/to/recording.mp3",
        file_size=512,
        duration=150,
        uploaded_at=datetime.now()
    )
    db_session.add(another_recording)
    await db_session.commit()
    await db_session.refresh(another_recording)

    response = await client.get(f"/api/v1/recordings/meeting/{test_meeting.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert all(r["meeting_id"] == test_meeting.id for r in data)

@pytest.mark.asyncio
async def test_get_recording(client: AsyncClient, auth_headers: dict, test_recording: Recording):
    response = await client.get(f"/api/v1/recordings/{test_recording.id}", headers=auth_headers)
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == test_recording.id
    assert data["file_path"] == test_recording.file_path

@pytest.mark.asyncio
async def test_update_recording(client: AsyncClient, auth_headers: dict, test_recording: Recording):
    new_status = "processing" # Use a valid status from RecordingStatus enum
    # Note: query parameters should be handled correctly by httpx, but let's double check validation
    response = await client.patch(
        f"/api/v1/recordings/{test_recording.id}/status",
        params={"new_status": new_status},
        headers=auth_headers
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["id"] == test_recording.id
    assert data["status"] == new_status

@pytest.mark.asyncio
async def test_delete_recording(client: AsyncClient, auth_headers: dict, test_recording: Recording, db_session: AsyncSession):
    recording_id = test_recording.id
    
    # Mock S3 deletion
    with patch("backend.app.utils.storage.storage_service.delete_from_s3", new_callable=AsyncMock) as mock_s3_delete:
        mock_s3_delete.return_value = True

        response = await client.delete(f"/api/v1/recordings/{recording_id}", headers=auth_headers)
        
        # Depending on implementation, delete might return 204 No Content
        assert response.status_code in [HTTPStatus.OK, HTTPStatus.NO_CONTENT] 
        
        # Verify S3 deletion was called
        mock_s3_delete.assert_called_once()

        recording_in_db = await db_session.execute(select(Recording).filter_by(id=recording_id))
        assert recording_in_db.scalar_one_or_none() is None

@pytest.mark.asyncio
async def test_get_recordings_eager_loading(db_session: AsyncSession, test_recording: Recording, test_meeting: Meeting, test_transcription: Transcription):
    from backend.app.services.recording_service import get_recordings_by_meeting
    
    # Retrieve recordings for the meeting, ensuring eager loading
    recordings = await get_recordings_by_meeting(db_session, meeting_id=test_meeting.id)

    assert len(recordings) > 0
    recording = recordings[0]

    # Access eager-loaded relationships
    # These accesses should not trigger additional database queries
    meeting_title = recording.meeting.title
    transcription_content = recording.transcription.transcribed_text if recording.transcription else None

    assert meeting_title == test_meeting.title
    if test_transcription:
        assert transcription_content == test_transcription.transcribed_text

    # More robust check for N+1 queries would involve mocking the DB session's execute method
    # and counting calls, similar to the note in test_pv.py for eager loading.