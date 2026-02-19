import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import sys
sys.path.insert(0, ".")
from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db, SessionLocal
from backend.app.api.deps import get_current_user, get_current_active_user, get_current_active_superuser
from backend.app.models.user import User, UserRole
from backend.app.models.meeting import Meeting, MeetingStatus
from backend.app.models.recording import Recording
from backend.app.models.transcription import Transcription, TranscriptionStatus
from backend.app.models.action import Action, ActionStatus
from backend.app.core.security import get_password_hash, create_access_token_for_user
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from celery import Celery

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=NullPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Create a new database session for each test and handle table creation/dropping.
    """
    print("Setting up db_session fixture...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = TestingSessionLocal(bind=engine)
    try:
        yield session
    finally:
        await session.close()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("Tearing down db_session fixture.")

@pytest.fixture(scope="function", autouse=True)
def patch_middleware_db():
    """
    Patch the SessionLocal in audit_middleware to use the test database engine.
    """
    with patch("backend.app.middleware.audit_middleware.SessionLocal", TestingSessionLocal):
        yield

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession, test_user: User, test_admin: User):
    """
    Create an asynchronous test client for the FastAPI application.
    """
    print("Setting up client fixture...")
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # Remove user overrides to allow testing with different users via tokens
    # app.dependency_overrides[get_current_user] = lambda: test_user
    # app.dependency_overrides[get_current_active_user] = lambda: test_user
    # app.dependency_overrides[get_current_active_superuser] = lambda: test_admin
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    print("Tearing down client fixture.")

@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession):
    password = "testpassword"
    hashed_password = get_password_hash(password)
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hashed_password,
        full_name="Test User",
        role=UserRole.PARTICIPANT,
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture(scope="function")
async def test_admin(db_session: AsyncSession):
    password = "adminpassword"
    hashed_password = get_password_hash(password)
    admin = User(
        username="adminuser",
        email="admin@example.com",
        hashed_password=hashed_password,
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
        is_superuser=True
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin

@pytest_asyncio.fixture(scope="function")
async def test_dg_user(db_session: AsyncSession):
    password = "dgpassword"
    hashed_password = get_password_hash(password)
    dg_user = User(
        username="dguser",
        email="dg@example.com",
        hashed_password=hashed_password,
        full_name="DG User",
        role=UserRole.DG,
        is_active=True,
        is_superuser=False
    )
    db_session.add(dg_user)
    await db_session.commit()
    await db_session.refresh(dg_user)
    return dg_user

@pytest_asyncio.fixture(scope="function")
async def auth_headers(test_user: User):
    # Access user_id immediately after refresh to prevent SQLAlchemy detached instance issues
    user_id = test_user.id
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token_for_user(
        user_id=user_id, expires_delta=access_token_expires
    )
    return {"Authorization": f"Bearer {token}"}

@pytest_asyncio.fixture(scope="function")
async def dg_headers(test_dg_user: User):
    user_id = test_dg_user.id
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token_for_user(
        user_id=user_id, expires_delta=access_token_expires
    )
    return {"Authorization": f"Bearer {token}"}

@pytest_asyncio.fixture(scope="function")
async def admin_headers(test_admin: User):
    # Access admin_id immediately after refresh to prevent SQLAlchemy detached instance issues
    admin_id = test_admin.id
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token_for_user(
        user_id=admin_id, expires_delta=access_token_expires
    )
    return {"Authorization": f"Bearer {token}"}

@pytest_asyncio.fixture(scope="function")
async def test_meeting(db_session: AsyncSession, test_user: User):
    meeting = Meeting(
        title="Test Meeting",
        description="Description for test meeting",
        date=datetime.now().date(),
        duration=60,
        location="Online",
        organizer_id=test_user.id,
        status=MeetingStatus.PLANNED
    )
    db_session.add(meeting)
    await db_session.commit()
    await db_session.refresh(meeting)
    return meeting

@pytest_asyncio.fixture(scope="function")
async def test_recording(db_session: AsyncSession, test_meeting: Meeting, test_user: User):
    recording = Recording(
        meeting_id=test_meeting.id,
        file_path="test/path/to/recording.mp3",
        file_size=1024,
        duration=300,
        uploaded_at=datetime.now(),
        uploader_id=test_user.id
    )
    db_session.add(recording)
    await db_session.commit()
    await db_session.refresh(recording)
    return recording

@pytest_asyncio.fixture(scope="function")
async def test_transcription(db_session: AsyncSession, test_meeting: Meeting, test_recording: Recording, test_user: User):
    transcription = Transcription(
        meeting_id=test_meeting.id,
        recording_id=test_recording.id,
        transcribed_text="This is a test transcription content.",
        language="en",
        status=TranscriptionStatus.COMPLETED,
        created_by_id=test_user.id
    )
    db_session.add(transcription)
    await db_session.commit()
    await db_session.refresh(transcription)
    return transcription

@pytest_asyncio.fixture(scope="function")
async def test_action(db_session: AsyncSession, test_meeting: Meeting, test_user: User):
    action = Action(
        meeting_id=test_meeting.id,
        description="Test action item",
        assigned_to=test_user.id,
        due_date=datetime.now().date() + timedelta(days=7),
        status=ActionStatus.PENDING
    )
    db_session.add(action)
    await db_session.commit()
    await db_session.refresh(action)
    return action

@pytest_asyncio.fixture(scope="function")
async def test_pv(db_session: AsyncSession, test_meeting: Meeting, test_user: User):
    from backend.app.models.pv import PV
    pv = PV(
        meeting_id=test_meeting.id,
        generated_by_id=test_user.id,
        title="Test PV Title",
        date=datetime.now().date(),
        participants=["Test User"],
        content="This is the full content of the PV.",
        decisions=["Decision 1", "Decision 2"],
        action_points=["Action 1 - Assigned to Test User - Due by 2026-03-01"],
        summary="This is a test PV summary.",
        raw_mistral_output="Raw Mistral output for testing."
    )
    db_session.add(pv)
    await db_session.commit()
    await db_session.refresh(pv)
    return pv

@pytest_asyncio.fixture(scope="function")
def mock_whisper():
    with patch("backend.app.services.whisper_client.whisper_client.call_whisper_api", new_callable=AsyncMock) as mock_transcribe:
        mock_transcribe.return_value = {"text": "Transcribed text", "language": "en"}
        yield mock_transcribe

@pytest_asyncio.fixture(scope="function")
def mock_mistral():
    with patch("backend.app.services.mistral_client.MistralClient.generate_pv", new_callable=AsyncMock) as mock_generate_pv, \
         patch("backend.app.services.mistral_client.MistralClient.extract_decisions", new_callable=AsyncMock) as mock_extract_decisions, \
         patch("backend.app.services.mistral_client.MistralClient.extract_action_items", new_callable=AsyncMock) as mock_extract_actions, \
         patch("backend.app.services.mistral_client.MistralClient.summarize_meeting", new_callable=AsyncMock) as mock_summarize:
        
        mock_generate_pv.return_value = "Mocked PV content."
        mock_extract_decisions.return_value = "Mocked decisions."
        mock_extract_actions.return_value = "Mocked action items."
        mock_summarize.return_value = "Mocked summary."
        yield {
            "generate_pv": mock_generate_pv,
            "extract_decisions": mock_extract_decisions,
            "extract_action_items": mock_extract_actions,
            "summarize_meeting": mock_summarize
        }

@pytest_asyncio.fixture(scope="function")
def mock_email():
    with patch("backend.app.services.notification_service.notification_service.send_email_notification", new_callable=AsyncMock) as mock_send_email_notification:
        yield mock_send_email_notification

@pytest_asyncio.fixture(scope="function")
async def mock_whatsapp():
    with patch("backend.app.services.notification_service.NotificationService.send_whatsapp_notification", new_callable=AsyncMock) as mock_send_whatsapp:
        yield mock_send_whatsapp

@pytest_asyncio.fixture(scope="function")
async def test_audit_log(db_session: AsyncSession, test_user: User):
    from backend.app.models.audit_log import AuditLog
    audit_log = AuditLog(
        user_id=test_user.id,
        action="LOGIN",
        resource_type="User",
        resource_id=str(test_user.id),
        timestamp=datetime.now(timezone.utc),
        details={"ip_address": "127.0.0.1", "user_agent": "pytest"}
    )
    db_session.add(audit_log)
    await db_session.commit()
    await db_session.refresh(audit_log)
    return audit_log

@pytest_asyncio.fixture(scope="function")
async def test_report(db_session: AsyncSession, test_meeting: Meeting, test_user: User):
    from backend.app.models.report import Report
    report = Report(
        meeting_id=test_meeting.id,
        generated_by_id=test_user.id,
        file_path="test/path/to/report.pdf",
        report_type="PDF",
        generated_at=datetime.now(timezone.utc)
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    return report

@pytest_asyncio.fixture(scope="session")
def celery_app_instance():
    """Provides a Celery app instance for testing."""
    # Ensure a consistent broker URL for testing
    celery_app_instance = Celery('test_celery_app', broker='redis://localhost:6379/1')
    celery_app_instance.conf.update(
        task_always_eager=True,  # Execute tasks locally without a worker
        task_eager_propagates=True,  # Propagate exceptions immediately
    )
    return celery_app_instance

@pytest_asyncio.fixture(scope="function")
def celery_app(celery_app_instance):
    """Fixture to provide the Celery app to tests."""
    # Clear tasks before each test
    celery_app_instance.control.purge()
    yield celery_app_instance

@pytest_asyncio.fixture(scope="function")
def celery_worker(celery_app):
    """Starts a Celery worker for the duration of the test."""
    with celery_app.test_worker() as worker:
        yield worker
