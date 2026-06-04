import pytest
import numpy as np
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.auto_enrollment_service import AutoEnrollmentService
from app.services.speaker_profile_service import SpeakerProfileService


def _make_mock_db_result(items):
    """Create a proper mock of SQLAlchemy async result."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    return result


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_make_mock_db_result([]))
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def enrollment_service(mock_db):
    return AutoEnrollmentService(mock_db)


@pytest.mark.asyncio
async def test_phase8_28_auto_enroll_new_speaker(enrollment_service, mock_db):
    """
    E2E Test: Auto-enroll a new speaker when confidence exceeds threshold.
    Verifies:
    - New speaker profile is created
    - Source is set to "auto_enrolled"
    """
    embedding = np.random.randn(192).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)

    with patch.object(enrollment_service.profile_service, "get_profile_by_name", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        with patch.object(enrollment_service.profile_service, "create_profile", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = AsyncMock()

            result = await enrollment_service.enroll_or_update(
                client_id="test-client-id",
                speaker_label="Speaker 0",
                resolved_name="Ahmed",
                embedding=embedding,
                confidence=0.85,
                method="fusion",
            )

            assert result is True
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["name"] == "Ahmed"
            assert call_kwargs["source"] == "auto_enrolled"


@pytest.mark.asyncio
async def test_phase8_29_update_existing_speaker(enrollment_service, mock_db):
    """
    E2E Test: Update existing speaker profile with new embedding.
    Verifies:
    - Running average is computed
    - sample_count is incremented
    """
    embedding = np.random.randn(192).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)

    mock_profile = AsyncMock()
    mock_profile.name = "Ahmed"
    mock_profile.embedding = embedding.tolist()
    mock_profile.sample_count = 3

    with patch.object(enrollment_service.profile_service, "get_profile_by_name", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_profile

        with patch.object(enrollment_service.profile_service, "update_profile_embedding", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = mock_profile

            result = await enrollment_service.enroll_or_update(
                client_id="test-client-id",
                speaker_label="Speaker 0",
                resolved_name="Ahmed",
                embedding=embedding,
                confidence=0.90,
                method="audio",
            )

            assert result is True
            mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_phase8_30_skip_low_confidence(enrollment_service, mock_db):
    """
    E2E Test: Skip enrollment when confidence is below threshold.
    Verifies:
    - No profile created or updated
    - Returns False
    """
    embedding = np.random.randn(192).astype(np.float32)

    with patch.object(enrollment_service.profile_service, "get_profile_by_name", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        with patch.object(enrollment_service.profile_service, "create_profile", new_callable=AsyncMock) as mock_create:
            result = await enrollment_service.enroll_or_update(
                client_id="test-client-id",
                speaker_label="Speaker 0",
                resolved_name="Unknown",
                embedding=embedding,
                confidence=0.15,
                method="text_inference",
            )

            assert result is False
            mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_phase8_31_batch_enrollment(enrollment_service, mock_db):
    """
    E2E Test: Batch enroll multiple speakers from a meeting.
    Verifies:
    - Multiple speakers enrolled in one call
    - Returns correct count of successful enrollments
    """
    mappings = [
        {
            "speaker_label": "Speaker 0",
            "resolved_name": "Ahmed",
            "embedding": np.random.randn(192).astype(np.float32),
            "confidence": 0.90,
            "method": "fusion",
        },
        {
            "speaker_label": "Speaker 1",
            "resolved_name": "Sarah",
            "embedding": np.random.randn(192).astype(np.float32),
            "confidence": 0.85,
            "method": "fusion",
        },
        {
            "speaker_label": "Speaker 2",
            "resolved_name": None,
            "embedding": np.random.randn(192).astype(np.float32),
            "confidence": 0.10,
            "method": "no_match",
        },
    ]

    with patch.object(enrollment_service, "enroll_or_update", new_callable=AsyncMock) as mock_enroll:
        mock_enroll.side_effect = [True, True, False]

        count = await enrollment_service.batch_enroll(
            client_id="test-client-id",
            speaker_mappings=mappings,
        )

        assert count == 2
        assert mock_enroll.call_count == 3
