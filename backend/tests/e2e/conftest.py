"""
E2E Test Configuration for Multi-Environment Testing.

Supports three environments:
- DEV: Local docker-compose.e2e.yml (default)
- STAGING: Kubernetes staging namespace (meeting-automation-staging)
- PRODUCTION: Kubernetes production namespace (meeting-automation)

Configuration via environment variables:
- TEST_ENV: dev|staging|production (default: dev)
- E2E_TEST_USER_EMAIL: Override test user email
- E2E_TEST_USER_PASSWORD: Override test user password
"""
import os
import io
import time
import uuid
import asyncio
from unittest.mock import AsyncMock, patch
from enum import Enum
from typing import Optional, AsyncGenerator, Dict, Any, List

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.transcription import Transcription
from app.models.pv import PV
from app.core.config import settings


class TestEnvironment(str, Enum):
    """Supported test environments."""

    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class EnvironmentConfig:
    """Configuration for different test environments."""

    def __init__(self):
        self.env = TestEnvironment(os.getenv("TEST_ENV", TestEnvironment.DEV))
        self.base_url = self._get_base_url()
        self.db_url = self._get_db_url()
        self.redis_url = self._get_redis_url()
        self.celery_broker_url = self._get_celery_broker_url()
        self.test_user_email = os.getenv(
            "E2E_TEST_USER_EMAIL",
            self._default_test_user_email()
        )
        self.test_user_password = os.getenv(
            "E2E_TEST_USER_PASSWORD",
            "TestPassword123!"
        )
        self.skip_cleanup = os.getenv("E2E_SKIP_CLEANUP", "").lower() == "true"

    def _get_base_url(self) -> str:
        """Get the base URL for the API depending on environment."""
        if self.env == TestEnvironment.STAGING:
            return "https://staging.meeting-automate.tn"
        elif self.env == TestEnvironment.PRODUCTION:
            return "https://meeting-automate.tn"
        else:
            # DEV: Connect to the backend service container in docker-compose.e2e.yml
            return "http://backend:8000"

    def _get_db_url(self) -> str:
        """Get database URL for direct DB access (bypassing API)."""
        if self.env == TestEnvironment.STAGING:
            return "postgresql+asyncpg://meeting_user:meeting_password@postgres-staging.meeting-automation-staging.svc.cluster.local:5432/meeting_db_staging"
        elif self.env == TestEnvironment.PRODUCTION:
            return None
        else:
            return "postgresql+asyncpg://meeting_user:meeting_password@postgres-test:5432/meeting_db_test"

    def _get_redis_url(self) -> str:
        """Get Redis URL for background tasks."""
        if self.env == TestEnvironment.STAGING:
            return "redis://:redis_password@redis-staging.meeting-automation-staging.svc.cluster.local:6379/0"
        elif self.env == TestEnvironment.PRODUCTION:
            return None
        else:
            return "redis://:redis_password@redis-test:6379/0"

    def _get_celery_broker_url(self) -> str:
        """Get Celery broker URL."""
        if self.env == TestEnvironment.STAGING:
            return "amqp://rabbit_user:rabbit_password@rabbitmq-staging.meeting-automation-staging.svc.cluster.local:5672//"
        elif self.env == TestEnvironment.PRODUCTION:
            return None
        else:
            return "amqp://rabbit_user:rabbit_password@rabbitmq-test:5672//"

    def _default_test_user_email(self) -> str:
        """Get default test user email for the environment."""
        if self.env == TestEnvironment.STAGING:
            return "e2e-tester-staging@meeting-automate.tn"
        elif self.env == TestEnvironment.PRODUCTION:
            return "e2e-smoke-tester@meeting-automate.tn"
        else:
            return "test@example.com"

    def requires_direct_db_access(self) -> bool:
        """Check if this environment allows direct DB access in tests."""
        return self.env != TestEnvironment.PRODUCTION

    def __str__(self) -> str:
        return f"EnvironmentConfig(env={self.env}, base_url={self.base_url})"


@pytest.fixture(scope="function")
def environment_config() -> EnvironmentConfig:
    """Provides the environment configuration for E2E tests."""
    return EnvironmentConfig()


@pytest_asyncio.fixture(scope="function")
async def e2e_client_no_auth(environment_config: EnvironmentConfig) -> AsyncGenerator[AsyncClient, None]:
    """Provides an unauthenticated HTTP client for E2E tests."""
    async with AsyncClient(base_url=environment_config.base_url, timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def e2e_client(
    environment_config: EnvironmentConfig,
    e2e_client_no_auth: AsyncClient,
    db_session: AsyncSession  # Ensure DB is initialized and test user exists
) -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an authenticated HTTP client for E2E tests.
    Uses test user credentials from environment or defaults.
    For DEV/STAGING: authenticates via login API (form-encoded).
    For PRODUCTION: expects pre-existing token or uses service account.
    """
    # For DEV and STAGING, perform login to obtain token
    if environment_config.env != TestEnvironment.PRODUCTION:
        # OAuth2PasswordRequestForm expects form data, not JSON
        login_data = {
            "username": environment_config.test_user_email,
            "password": environment_config.test_user_password
        }
        resp = await e2e_client_no_auth.post("/api/v1/auth/login", data=login_data)
        resp.raise_for_status()
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(base_url=environment_config.base_url, headers=headers, timeout=30.0) as auth_client:
            yield auth_client
    else:
        import warnings
        warnings.warn("Production E2E tests should use PROD_ADMIN_EMAIL/PASSWORD via GitHub Secrets")
        yield e2e_client_no_auth


# ==================== Comprehensive E2E Fixtures ====================

@pytest.fixture
def sample_audio_bytes() -> bytes:
    """Returns a minimal audio file content for recording uploads."""
    # 1 second of silence as WAV (simple header + data)
    # For E2E tests, content doesn't matter because Gladia is mocked.
    return b"FAKE_AUDIO_DATA_FOR_E2E_TESTING"


@pytest.fixture
def mock_gladia():
    """
    Mocks GladiaService.transcribe_and_diarize to return deterministic results.
    This prevents real API calls and speeds up tests.
    """
    mock_result = {
        "full_text": "Speaker 1: Hello, this is a test transcription. Speaker 2: Hi, welcome to the meeting.",
        "segments": [
            {"speaker": "Speaker 1", "text": "Hello, this is a test transcription.", "start": 0.0, "end": 3.0},
            {"speaker": "Speaker 2", "text": "Hi, welcome to the meeting.", "start": 3.0, "end": 6.0},
        ]
    }
    with patch(
        "app.services.gladia_service.gladia_service.transcribe_and_diarize",
        new=AsyncMock(return_value=mock_result)
    ) as m:
        yield m


@pytest.fixture
def mock_mistral_pv():
    """
    Mocks PVService.generate_pv to return deterministic PV data.
    Prevents real Mistral API calls.
    """
    mock_pv_data = {
        "title": "E2E Test Meeting PV",
        "tags": "e2e, test, automation",
        "summary": "Discussion about E2E test infrastructure and automation strategies.",
        "decisions": ["Adopt comprehensive E2E fixtures", "Implement external API mocking"],
        "actions": [
            {
                "description": "Create comprehensive E2E fixtures",
                "priority": "high",
                "priority_reason": "Critical for test stability",
                "assignee": "Test Engineer",
                "deadline": "2026-12-31"
            },
            {
                "description": "Mock external APIs for deterministic tests",
                "priority": "high",
                "priority_reason": "Required for CI reliability",
                "assignee": "DevOps",
                "deadline": "2026-11-30"
            }
        ]
    }
    with patch(
        "app.services.pv_service.PVService.generate_pv",
        new=AsyncMock(return_value=mock_pv_data)
    ) as m:
        yield m


@pytest.fixture
def mock_n8n_transcription():
    """
    Mocks the _notify_n8n_completion function used in transcription pipeline.
    Prevents webhook calls during recording processing.
    """
    with patch(
        "app.tasks.transcription_tasks._notify_n8n_completion",
        new=AsyncMock()
    ) as m:
        yield m


@pytest.fixture
def mock_n8n_action():
    """
    Mocks n8n webhook calls in action_service (status updates, escalations)
    by intercepting httpx.AsyncClient.post. Returns a mock object that can be
    used to assert calls (.called, .await_count, etc.).
    """
    import httpx
    original_post = httpx.AsyncClient.post
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "ok"}

    # Create a mock for the post method that we can track
    mock_post = AsyncMock(return_value=mock_response)

    async def selective_mock(self, *args, **kwargs):
        url = args[0] if args else kwargs.get('url')
        n8n_url = settings.N8N_WEBHOOK_URL
        # If N8N_WEBHOOK_URL is not set, mock all httpx.post calls
        # If it is set, only mock calls to that URL
        if not n8n_url:
            return await mock_post(*args, **kwargs)
        if url and (n8n_url in str(url)):
            return await mock_post(*args, **kwargs)
        return await original_post(self, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "post", selective_mock):
        yield mock_post


@pytest.fixture
def mock_sentinel():
    """
    Mocks sentinel.summarize_chunk to return deterministic summary.
    Prevents real API calls to external LLM service.
    """
    with patch(
        "app.services.sentinel_service.sentinel.summarize_chunk",
        new=AsyncMock(return_value="Mocked summary: This is a short summary of the chunk.")
    ) as m:
        yield m


@pytest_asyncio.fixture
async def e2e_meeting(e2e_client: AsyncClient) -> Dict[str, Any]:
    """
    Creates a meeting via API and returns the meeting dictionary.
    Automatically cleaned up via DB transaction rollback.
    """
    meeting_data = {
        "title": "E2E Test Meeting",
        "description": "Meeting created by e2e_meeting fixture for comprehensive testing",
        "start_time": "2026-04-04T10:00:00",
        "end_time": "2026-04-04T11:00:00",
        "location": "Test Location",
        "participants": []
    }
    resp = await e2e_client.post("/api/v1/meetings/", json=meeting_data)
    resp.raise_for_status()
    meeting = resp.json()
    return meeting


@pytest_asyncio.fixture
async def e2e_recording(
    e2e_client: AsyncClient,
    e2e_meeting: Dict[str, Any],
    sample_audio_bytes: bytes,
    mock_gladia,
    mock_mistral_pv,
    mock_sentinel,
    mock_n8n_transcription
) -> Dict[str, Any]:
    """
    Uploads a recording for the given meeting.
    Triggers the transcription pipeline (with mocked external APIs) DIRECTLY to avoid Celery registration issues.
    Returns the recording dictionary.
    """
    meeting_id = e2e_meeting["id"]
    files = {"file": ("test_recording.wav", sample_audio_bytes, "audio/wav")}
    resp = await e2e_client.post(f"/api/v1/recordings/upload/{meeting_id}", files=files)
    resp.raise_for_status()
    recording = resp.json()

    # Directly trigger the pipeline (bypass Celery) to ensure it runs in same async context
    from app.tasks.transcription_tasks import _process_recording_pipeline
    await _process_recording_pipeline(recording["id"])

    return recording


@pytest_asyncio.fixture
async def e2e_transcription(
    e2e_recording: Dict[str, Any],
    db_session: AsyncSession,
    mock_gladia,
    mock_mistral_pv,
    mock_sentinel,
    mock_n8n_transcription
) -> Dict[str, Any]:
    """
    Waits for the transcription (and PV) to be created after recording upload.
    Returns the transcription dictionary.
    """
    recording_id = e2e_recording["id"]
    meeting_id = e2e_recording["meeting_id"]

    timeout = 60  # 1 minute max (with mocked external APIs, Celery eager mode)
    interval = 0.5  # poll faster
    start_time = time.time()
    transcription = None

    # Pipeline committed in a separate AsyncSessionLocal(); expire cache so this
    # session sees the newly committed rows on the first query.
    db_session.expire_all()

    while time.time() - start_time < timeout:
        result = await db_session.execute(
            select(Transcription).where(Transcription.recording_id == recording_id)
        )
        transcription = result.scalar_one_or_none()
        if transcription:
            # Transcription exists; pipeline likely completed.
            # Optionally also check PV existence.
            pv_result = await db_session.execute(
                select(PV).where(PV.meeting_id == meeting_id)
            )
            pv = pv_result.scalar_one_or_none()
            if pv:
                # All done
                break
        await asyncio.sleep(interval)

    if transcription is None:
        raise TimeoutError(f"Transcription for recording {recording_id} was not created within {timeout}s")

    return {
        "id": transcription.id,
        "recording_id": transcription.recording_id,
        "meeting_id": transcription.meeting_id,
        "full_text": transcription.full_text,
        "segments": transcription.segments or [],
        "language": transcription.language,
    }


@pytest_asyncio.fixture
async def e2e_pv(
    e2e_transcription: Dict[str, Any],
    db_session: AsyncSession
) -> Dict[str, Any]:
    """
    Retrieves the PV generated for the meeting associated with the e2e_transcription.
    Returns the PV dictionary.
    """
    meeting_id = e2e_transcription["meeting_id"]
    db_session.expire_all()  # ensure fresh read after pipeline commit
    result = await db_session.execute(
        select(PV).where(PV.meeting_id == meeting_id)
    )
    pv = result.scalar_one_or_none()
    if pv is None:
        raise ValueError(f"No PV found for meeting {meeting_id}")

    return {
        "id": pv.id,
        "meeting_id": pv.meeting_id,
        "title": pv.title,
        "tags": pv.tags,
        "content_html": pv.content_html,
        "status": pv.status,
        "language": pv.language,
        "is_validated": pv.is_validated,
    }
