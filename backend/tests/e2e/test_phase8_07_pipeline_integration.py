import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import numpy as np

from app.tasks.transcription_tasks import _identify_speakers


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
def mock_gladia_result():
    return {
        "segments": [
            {"speaker": "Speaker 0", "text": "Hello, I'm Ahmed.", "start": 0.0, "end": 3.0},
            {"speaker": "Speaker 0", "text": "Let me share my screen.", "start": 5.0, "end": 8.0},
            {"speaker": "Speaker 1", "text": "Hi Ahmed, I'm Sarah.", "start": 10.0, "end": 13.0},
            {"speaker": "Speaker 1", "text": "I can see your presentation.", "start": 15.0, "end": 18.0},
        ],
        "full_text": "Hello, I'm Ahmed. Let me share my screen. Hi Ahmed, I'm Sarah. I can see your presentation.",
    }


@pytest.mark.asyncio
async def test_phase8_32_identify_speakers_full_pipeline(mock_db, mock_gladia_result):
    """
    E2E Test: Full speaker identification pipeline with consensus across sources.
    Verifies:
    - Audio embedding extraction called
    - Profile matching returns high-confidence result
    - Regex self-introduction detected
    - Consensus aggregation across audio+text sources
    - Auto-enrollment triggered
    - Returns correct mappings
    """
    embedding = np.random.randn(192).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)

    with patch("app.tasks.transcription_tasks._extract_speaker_embedding", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = embedding

        with patch("app.tasks.transcription_tasks.SpeakerProfileService") as mock_profile_cls:
            mock_profile_instance = AsyncMock()
            # Return different names for different speakers
            mock_profile_instance.match_speaker = AsyncMock(side_effect=[
                ("Ahmed", 0.15, "high"),
                ("Sarah", 0.18, "high"),
            ])
            mock_profile_instance.get_profiles = AsyncMock(return_value=[])
            mock_profile_cls.return_value = mock_profile_instance

            with patch("app.tasks.transcription_tasks.AutoEnrollmentService") as mock_enrollment_cls:
                mock_enrollment_instance = AsyncMock()
                mock_enrollment_instance.enroll_or_update = AsyncMock(return_value=True)
                mock_enrollment_cls.return_value = mock_enrollment_instance

                mappings = await _identify_speakers(
                    db=mock_db,
                    gladia_result=mock_gladia_result,
                    client_id="test-client-id",
                    recording_id="test-recording-id",
                    temp_path="/tmp/test.wav",
                    meeting_id="test-meeting-id",
                    participant_names=["Ahmed", "Sarah"],
                )

                assert len(mappings) == 2
                assert mappings[0]["speaker_label"] == "Speaker 0"
                assert mappings[0]["resolved_name"] == "Ahmed"
                assert mappings[0]["confidence"] >= 0.90
                assert "audio" in mappings[0]["method"]
                assert "text" in mappings[0]["method"]

                assert mappings[1]["speaker_label"] == "Speaker 1"
                assert mappings[1]["resolved_name"] == "Sarah"
                assert mappings[1]["confidence"] >= 0.90
                assert "audio" in mappings[1]["method"]
                assert "text" in mappings[1]["method"]

                assert mock_extract.call_count == 2
                assert mock_enrollment_instance.enroll_or_update.call_count == 2


@pytest.mark.asyncio
async def test_phase8_33_identify_speakers_no_segments(mock_db):
    """
    E2E Test: Handles empty segments gracefully.
    Verifies:
    - Returns empty list when no segments
    - No errors raised
    """
    mappings = await _identify_speakers(
        db=mock_db,
        gladia_result={"segments": []},
        client_id="test-client-id",
        recording_id="test-recording-id",
        temp_path="/tmp/test.wav",
        meeting_id="test-meeting-id",
        participant_names=[],
    )

    assert mappings == []


@pytest.mark.asyncio
async def test_phase8_34_identify_speakers_embedding_unavailable(mock_db, mock_gladia_result):
    """
    E2E Test: Falls back to text-only when embedding unavailable.
    Verifies:
    - Embedding extraction returns None
    - Regex self-introduction detects names from text
    - Returns correct mappings with method=text
    """
    with patch("app.tasks.transcription_tasks._extract_speaker_embedding", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = None

        with patch("app.tasks.transcription_tasks.SpeakerProfileService") as mock_profile_cls:
            mock_profile_instance = AsyncMock()
            mock_profile_instance.get_profiles = AsyncMock(return_value=[])
            mock_profile_cls.return_value = mock_profile_instance

            with patch("app.tasks.transcription_tasks.AutoEnrollmentService") as mock_enrollment_cls:
                mock_enrollment_instance = AsyncMock()
                mock_enrollment_instance.enroll_or_update = AsyncMock(return_value=True)
                mock_enrollment_cls.return_value = mock_enrollment_instance

                mappings = await _identify_speakers(
                    db=mock_db,
                    gladia_result=mock_gladia_result,
                    client_id="test-client-id",
                    recording_id="test-recording-id",
                    temp_path="/tmp/test.wav",
                    meeting_id="test-meeting-id",
                    participant_names=["Ahmed", "Sarah"],
                )

                assert len(mappings) == 2
                assert mappings[0]["speaker_label"] == "Speaker 0"
                assert mappings[0]["resolved_name"] == "Ahmed"
                assert mappings[0]["method"] == "heuristic+text"

                assert mappings[1]["speaker_label"] == "Speaker 1"
                assert mappings[1]["resolved_name"] == "Sarah"
                assert mappings[1]["method"] == "text"

                assert mock_extract.call_count == 2
