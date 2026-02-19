import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.meeting import Meeting, MeetingStatus
from backend.app.models.user import User, UserRole
from backend.app.schemas.meeting import MeetingCreate, MeetingUpdate
from backend.app.schemas.recording import RecordingCreate
from backend.app.schemas.transcription import TranscriptionCreate
from backend.app.schemas.pv import PVCreate
from backend.app.schemas.action import ActionCreate
from backend.app.services.meeting_service import meeting_service
from backend.app.services.recording_service import create_recording as recording_service_create_recording
from backend.app.services.transcription_service import transcription_service
from backend.app.services.pv_service import generate_pv as pv_service_generate_pv
from backend.app.services.action_service import action_service
from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
import logging
import json
from http import HTTPStatus

# Configure logging for tests to capture SQL queries
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper to count DB queries (simplified, for demonstration)
# In a real scenario, a more robust DB query logger/monitor would be used.
class QueryCounter:
    def __init__(self):
        self.count = 0
    def __call__(self, *args, **kwargs):
        self.count += 1

# Patch the SQLAlchemy execute method to count queries
@pytest_asyncio.fixture
async def db_query_counter(db_session: AsyncSession):
    counter = QueryCounter()
    original_execute = db_session.execute
    async def mock_execute(*args, **kwargs):
        counter.count += 1
        return await original_execute(*args, **kwargs)
    db_session.execute = mock_execute
    yield counter
    db_session.execute = original_execute # Restore original method

@pytest.mark.asyncio
async def test_create_meeting(client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession):
    meeting_data = MeetingCreate(
        title="New Test Meeting",
        description="Description for new test meeting",
            date=datetime.now() + timedelta(days=1),
        duration=90,
        location="Zoom",
        organizer_id=test_user.id
    )
    # Use jsonable_encoder-like behavior or just dict() with string conversion for datetime
    # Since .json() seems to be causing issues or maybe it's a different issue, let's try a safer approach
    # Convert datetime to string manually for the test payload
    payload = meeting_data.dict()
    payload["date"] = payload["date"].isoformat()
    
    response = await client.post("/api/v1/meetings/", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["title"] == "New Test Meeting"
    assert data["organizer_id"] == test_user.id
    assert data["status"] == MeetingStatus.PLANNED.value

    # Verify meeting in database
    meeting_in_db = await db_session.execute(select(Meeting).filter_by(id=data["id"]))
    meeting = meeting_in_db.scalar_one_or_none()
    assert meeting is not None
    assert meeting.title == "New Test Meeting"

@pytest.mark.asyncio
async def test_meeting_eager_loading(client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession, db_query_counter: QueryCounter):
    """
    TESTFALL_ML01: Test Meeting-Service Eager Loading.
    Prüfen ob alle Meeting-Beziehungen korrekt geladen werden.
    """
    # 1. Meeting mit organizer, recordings, transcriptions, pvs, actions erstellen.
    meeting_data = MeetingCreate(
        title="Eager Load Test Meeting",
        description="Description for eager load test meeting",
        date=datetime.now() + timedelta(days=1),
        duration=60,
        location="Test Location",
        organizer_id=test_user.id
    )
    meeting = await meeting_service.create_meeting(db_session, meeting_data, test_user.id)
    await db_session.refresh(meeting)

    # Create related objects
    recording_data = RecordingCreate(
        meeting_id=meeting.id,
        file_path="path/to/recording.mp3",
        file_size=1024,
        file_type="audio/mpeg",
        uploader_id=test_user.id,
        duration=10.0
    )
    recording = await recording_service_create_recording(db_session, recording_data)
    await db_session.refresh(recording)

    # `create_transcription` does not exist, use `start_transcription` instead
    # The transcription content is set by the service after calling whisper API, not directly in creation.
    # Mock the whisper client call to avoid network errors
    with patch("backend.app.services.whisper_client.WhisperClient.call_whisper_api", new_callable=AsyncMock) as mock_whisper:
        mock_whisper.return_value = {
            "text": "Transcription content for eager load test.",
            "language": "en",
            "duration": 10.0,
            "segments": [],
            "word_timestamps": []
        }
        transcription = await transcription_service.start_transcription(
            db=db_session,
            recording_id=recording.id,
            current_user_id=test_user.id,
            language="en",  # Default language for test
            enable_diarization=False # Default for test
        )
    await db_session.refresh(transcription)

    pv_data = PVCreate(
        title="PV Title",
        meeting_id=meeting.id,
        content="PV content for eager load test.",
        decisions=["Decision 1"],
        actions=["Action 1"],
        validated_by_id=test_user.id
    )
    # The generate_pv function in pv_service expects meeting_id, transcription_id, template, db, current_user
    # For testing purposes, we'll mock the transcription and current_user
    # This is a simplified call for the test, a real scenario might involve more setup
    # Also mock mistral client for PV generation if needed, assuming generate_pv might use it
    with patch("backend.app.services.mistral_client.MistralClient.generate_pv", new_callable=AsyncMock) as mock_mistral_generate, \
         patch("backend.app.services.pv_service.extract_decisions", new_callable=AsyncMock) as mock_extract_decisions, \
         patch("backend.app.services.pv_service.extract_action_points", new_callable=AsyncMock) as mock_extract_actions:
        
        mock_mistral_generate.return_value = "PV content for eager load test."
        mock_extract_decisions.return_value = "Decision 1"
        mock_extract_actions.return_value = "Action 1"
        
        pv = await pv_service_generate_pv(
            meeting_id=meeting.id,
            transcription_id=transcription.id,
            db=db_session,
            current_user=test_user
        )
    await db_session.refresh(pv)

    action_data = ActionCreate(
        meeting_id=meeting.id,
        description="Test action item.",
        assigned_to=test_user.id,
        due_date=datetime.now() + timedelta(days=7)
    )
    action = await action_service.create_action(db_session, action_data, current_user=test_user)
    await db_session.refresh(action)

    # Clear query counter before the main fetch
    db_query_counter.count = 0

    # 2. `meeting = await meeting_service.get_meeting_by_id(db, meeting_id)` aufrufen.
    # This should trigger the eager loading.
    initial_query_count = db_query_counter.count
    loaded_meeting = await meeting_service.get_meeting_by_id(db_session, meeting.id)
    query_count_after_initial_load = db_query_counter.count

    assert loaded_meeting is not None
    # Expect only one query for the initial load (or a few if relationships are loaded separately but still eagerly)
    # The exact number depends on the eager loading implementation in meeting_service.get_meeting_by_id
    # For this test, we primarily care that subsequent accesses don't trigger *new* queries.
    assert query_count_after_initial_load > initial_query_count # Ensure at least one query happened

    # Reset counter to check for N+1 queries
    db_query_counter.count = 0

    # 3. Prüfen: `meeting.organizer.name` (sollte keinen zusätzlichen DB-Call auslösen)
    assert loaded_meeting.organizer.full_name == test_user.full_name
    assert db_query_counter.count == 0, "Accessing organizer triggered an N+1 query"

    # 4. Prüfen: `len(meeting.recordings)` (sollte keinen zusätzlichen DB-Call auslösen)
    assert len(loaded_meeting.recordings) == 1
    assert loaded_meeting.recordings[0].file_path == recording.file_path
    assert db_query_counter.count == 0, "Accessing recordings triggered an N+1 query"

    # 5. Prüfen: `meeting.recordings[0].transcription` (sollte keinen zusätzlichen DB-Call auslösen)
    # Note: Transcriptions are related to Recordings, not directly to Meeting.
    # We need to access it via the recording.
    assert loaded_meeting.recordings[0].transcription is not None
    # transcription.content was renamed to transcribed_text in model
    assert loaded_meeting.recordings[0].transcription.transcribed_text == transcription.transcribed_text
    assert db_query_counter.count == 0, "Accessing transcriptions via recording triggered an N+1 query"

    # 6. Prüfen: `meeting.pv.content` (sollte keinen zusätzlichen DB-Call auslösen)
    assert loaded_meeting.pv is not None
    assert loaded_meeting.pv.content == pv.content
    assert db_query_counter.count == 0, "Accessing PVs triggered an N+1 query"

    # 7. Prüfen: `meeting.actions[0].description` (sollte keinen zusätzlichen DB-Call auslösen)
    assert len(loaded_meeting.actions) == 1
    assert loaded_meeting.actions[0].description == action.description
    assert db_query_counter.count == 0, "Accessing actions triggered an N+1 query"

    logger.info(f"TESTFALL_ML01: Meeting Eager Loading - Initial queries: {query_count_after_initial_load - initial_query_count}, N+1 queries: {db_query_counter.count}")

@pytest.mark.asyncio
async def test_list_meetings(client: AsyncClient, auth_headers: dict, test_meeting: Meeting, test_user: User, db_session: AsyncSession):
    # Create another meeting for filtering
    another_user = User(
        username="anotheruser_meeting",
        email="another_meeting@example.com",
        hashed_password="hashedpassword".encode("utf-8"),
        full_name="Another User Meeting",
        role=UserRole.PARTICIPANT,
        is_active=True,
        is_superuser=False
    )
    db_session.add(another_user)
    await db_session.commit()
    await db_session.refresh(another_user)

    another_meeting = Meeting(
        title="Another Meeting",
        description="Description for another meeting",
        date=datetime.now() + timedelta(days=2),
        duration=45,
        location="Teams",
        organizer_id=another_user.id,
        status=MeetingStatus.COMPLETED
    )
    db_session.add(another_meeting)
    await db_session.commit()
    await db_session.refresh(another_meeting)

    # Test listing all meetings
    response = await client.get("/api/v1/meetings/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2 # At least test_meeting and another_meeting

    # Test listing with filter by status
    response = await client.get(f"/api/v1/meetings/?status={MeetingStatus.PLANNED.value}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(m["status"] == MeetingStatus.PLANNED.value for m in data)

    # Test listing with filter by organizer_id
    response = await client.get(f"/api/v1/meetings/?organizer_id={test_user.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(m["organizer_id"] == test_user.id for m in data)

@pytest.mark.asyncio
async def test_get_meeting(client: AsyncClient, auth_headers: dict, test_meeting: Meeting):
    response = await client.get(f"/api/v1/meetings/{test_meeting.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_meeting.id
    assert data["title"] == test_meeting.title

@pytest.mark.asyncio
async def test_update_meeting_as_organizer(client: AsyncClient, auth_headers: dict, test_meeting: Meeting):
    update_data = MeetingUpdate(
        title="Updated Test Meeting",
        description="Updated description",
        duration=120
    )
    response = await client.put(f"/api/v1/meetings/{test_meeting.id}", json=update_data.dict(exclude_unset=True), headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Test Meeting"
    assert data["description"] == "Updated description"
    assert data["duration"] == 120

@pytest.mark.asyncio
async def test_update_meeting_as_other_user_403(client: AsyncClient, db_session: AsyncSession, test_meeting: Meeting):
    other_user = User(
        username="otheruser_update",
        email="other_update@example.com",
        hashed_password="hashedpassword".encode("utf-8"),
        full_name="Other User Update",
        role=UserRole.PARTICIPANT,
        is_active=True,
        is_superuser=False
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    other_user_token = create_access_token(
        data={"sub": str(other_user.id)}, expires_delta=access_token_expires
    )
    other_user_headers = {"Authorization": f"Bearer {other_user_token}"}

    update_data = MeetingUpdate(title="Unauthorized Update")
    response = await client.put(f"/api/v1/meetings/{test_meeting.id}", json=update_data.dict(exclude_unset=True), headers=other_user_headers)
    assert response.status_code == 403
    assert "Not authorized to update this meeting" in response.json()["detail"]

@pytest.mark.asyncio
async def test_delete_meeting_as_organizer(client: AsyncClient, auth_headers: dict, test_meeting: Meeting, db_session: AsyncSession):
    meeting_id = test_meeting.id
    response = await client.delete(f"/api/v1/meetings/{meeting_id}", headers=auth_headers)
    assert response.status_code == 204
    
    # Verify deletion
    meeting_in_db = await db_session.execute(select(Meeting).filter_by(id=meeting_id))
    assert meeting_in_db.scalar_one_or_none() is None

@pytest.mark.asyncio
async def test_delete_meeting_as_admin(client: AsyncClient, admin_headers: dict, test_meeting: Meeting, db_session: AsyncSession):
    meeting_id = test_meeting.id
    response = await client.delete(f"/api/v1/meetings/{meeting_id}", headers=admin_headers)
    assert response.status_code == 204
    
    # Verify deletion
    meeting_in_db = await db_session.execute(select(Meeting).filter_by(id=meeting_id))
    assert meeting_in_db.scalar_one_or_none() is None

@pytest.mark.asyncio
async def test_delete_meeting_as_other_user_403(client: AsyncClient, db_session: AsyncSession, test_meeting: Meeting):
    other_user = User(
        username="otheruser_delete",
        email="other_delete@example.com",
        hashed_password="hashedpassword".encode("utf-8"),
        full_name="Other User Delete",
        role=UserRole.PARTICIPANT,
        is_active=True,
        is_superuser=False
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    other_user_token = create_access_token(
        data={"sub": str(other_user.id)}, expires_delta=access_token_expires
    )
    other_user_headers = {"Authorization": f"Bearer {other_user_token}"}

    response = await client.delete(f"/api/v1/meetings/{test_meeting.id}", headers=other_user_headers)
    assert response.status_code == 403
    assert "Not authorized to delete this meeting" in response.json()["detail"]

@pytest.mark.asyncio
async def test_change_meeting_status(client: AsyncClient, auth_headers: dict, test_meeting: Meeting):
    # status is a query parameter in the endpoint definition
    response = await client.patch(
        f"/api/v1/meetings/{test_meeting.id}/status",
        params={"status": MeetingStatus.COMPLETED.value},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == MeetingStatus.COMPLETED.value

@pytest.mark.asyncio
async def test_list_meetings_pagination(client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_user: User):
    # Create multiple meetings for pagination test
    for i in range(10):
        meeting = Meeting(
            title=f"Paginated Meeting {i}",
            description=f"Description {i}",
            date=datetime.now() + timedelta(days=i),
            duration=60,
            location="Online",
            organizer_id=test_user.id,
            status=MeetingStatus.PLANNED
        )
        db_session.add(meeting)
    await db_session.commit()

    # Test first page with limit 5
    response = await client.get("/api/v1/meetings/?skip=0&limit=5", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5

    # Test second page with limit 5
    response = await client.get("/api/v1/meetings/?skip=5&limit=5", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5