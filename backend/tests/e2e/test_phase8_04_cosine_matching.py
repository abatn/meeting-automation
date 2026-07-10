"""
Phase 8: Speaker Identification — E2E Tests
Phase 4: Cosine Distance Matching against stored profiles
"""
import os
import tempfile
import wave
import uuid

import numpy as np
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.services.audio_segment_service import AudioSegmentService
from app.services.speaker_embedding_service import SpeakerEmbeddingService, SAMPLE_RATE
from app.services.speaker_profile_service import SpeakerProfileService


def _generate_test_audio_file(
    duration_seconds: float = 6.0,
    frequency: float = 440.0,
) -> str:
    """Generate a WAV file with a sine wave tone."""
    n_samples = int(SAMPLE_RATE * duration_seconds)
    t = np.linspace(0, duration_seconds, n_samples, dtype=np.float32)
    audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)
    audio = (audio * 32767).astype(np.int16)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())

    return tmp.name


@pytest.fixture
def test_audio_file():
    """Generate a 6-second test audio file."""
    path = _generate_test_audio_file(duration_seconds=6.0, frequency=440.0)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def test_audio_file_different():
    """Generate a 6-second test audio file with different frequency."""
    path = _generate_test_audio_file(duration_seconds=6.0, frequency=880.0)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def sample_segments():
    """Sample Gladia diarization segments."""
    return [
        {"speaker": "Speaker 0", "text": "Hello everyone", "start": 0.0, "end": 3.0},
        {"speaker": "Speaker 0", "text": "Let's continue", "start": 3.0, "end": 6.0},
    ]


@pytest.mark.asyncio
async def test_phase8_18_enroll_and_match_same_speaker(db_session, test_audio_file, sample_segments):
    """
    E2E Test: Enroll a speaker from audio, then match the same speaker.
    Verifies:
    - Audio → Embedding → Enrollment works
    - Same audio matches the enrolled profile with high confidence
    """
    import uuid
    from datetime import datetime
    from app.models.client import Client
    
    embedding_service = SpeakerEmbeddingService()
    await embedding_service.initialize()

    if not embedding_service.is_available:
        pytest.skip("SpeakerEmbeddingService not available")

    profile_service = SpeakerProfileService(db_session)

    # Create a test client
    client = Client(
        id=str(uuid.uuid4()),
        company_name=f"Test Company {uuid.uuid4().hex[:6]}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        created_at=datetime.utcnow(),
    )
    db_session.add(client)
    await db_session.flush()

    embedding = await embedding_service.extract_embedding(test_audio_file)
    assert embedding is not None, "Embedding should be extracted"

    speaker = await profile_service.create_profile(
        client_id=client.id,
        name="Ahmed",
        embedding=embedding,
        source="manual",
    )
    await db_session.commit()

    name, distance, confidence = await profile_service.match_speaker(
        client_id=client.id,
        embedding=embedding,
    )

    assert name == "Ahmed", f"Expected 'Ahmed', got {name}"
    assert distance < 0.10, f"Same embedding should have distance < 0.10, got {distance}"
    assert confidence in ("high", "medium"), f"Expected high/medium confidence, got {confidence}"


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="ONNX model trained on speech — synthetic audio produces degenerate embeddings. "
           "Requires model retraining with corrected fbank features (Phase 157 RC1 Provenance).",
    strict=False,
)
async def test_phase8_19_enroll_and_match_different_speaker(
    db_session, test_audio_file, test_audio_file_different, sample_segments
):
    """
    E2E Test: Enroll a speaker, then try to match a different audio.
    Verifies:
    - Different audio produces different embedding
    - Distance is higher than same-speaker match
    """
    import uuid
    from datetime import datetime
    from app.models.client import Client
    
    embedding_service = SpeakerEmbeddingService()
    await embedding_service.initialize()

    if not embedding_service.is_available:
        pytest.skip("SpeakerEmbeddingService not available")

    profile_service = SpeakerProfileService(db_session)

    # Create a test client
    client = Client(
        id=str(uuid.uuid4()),
        company_name=f"Test Company {uuid.uuid4().hex[:6]}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        created_at=datetime.utcnow(),
    )
    db_session.add(client)
    await db_session.flush()

    embedding_ahmed = await embedding_service.extract_embedding(test_audio_file)
    assert embedding_ahmed is not None

    await profile_service.create_profile(
        client_id=client.id,
        name="Ahmed",
        embedding=embedding_ahmed,
        source="manual",
    )
    await db_session.commit()

    embedding_sarah = await embedding_service.extract_embedding(test_audio_file_different)
    assert embedding_sarah is not None

    name, distance, confidence = await profile_service.match_speaker(
        client_id=client.id,
        embedding=embedding_sarah,
    )

    assert name == "Ahmed", f"Should still match Ahmed (only profile), got {name}"
    assert distance > 0.05, f"Different audio should have distance > 0.05, got {distance}"


@pytest.mark.asyncio
async def test_phase8_20_multi_speaker_matching(db_session, test_audio_file, test_audio_file_different):
    """
    E2E Test: Match against multiple enrolled speakers.
    Verifies:
    - Correct speaker is matched (closest embedding)
    - Multiple profiles don't interfere
    """
    import uuid
    from datetime import datetime
    from app.models.client import Client
    
    embedding_service = SpeakerEmbeddingService()
    await embedding_service.initialize()

    if not embedding_service.is_available:
        pytest.skip("SpeakerEmbeddingService not available")

    profile_service = SpeakerProfileService(db_session)

    # Create a test client
    client = Client(
        id=str(uuid.uuid4()),
        company_name=f"Test Company {uuid.uuid4().hex[:6]}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        created_at=datetime.utcnow(),
    )
    db_session.add(client)
    await db_session.flush()

    embedding_ahmed = await embedding_service.extract_embedding(test_audio_file)
    embedding_sarah = await embedding_service.extract_embedding(test_audio_file_different)

    await profile_service.create_profile(
        client_id=client.id,
        name="Ahmed",
        embedding=embedding_ahmed,
        source="manual",
    )
    await profile_service.create_profile(
        client_id=client.id,
        name="Sarah",
        embedding=embedding_sarah,
        source="manual",
    )
    await db_session.commit()

    name_ahmed, dist_ahmed, _ = await profile_service.match_speaker(
        client_id=client.id,
        embedding=embedding_ahmed,
    )
    name_sarah, dist_sarah, _ = await profile_service.match_speaker(
        client_id=client.id,
        embedding=embedding_sarah,
    )

    assert name_ahmed == "Ahmed", f"Ahmed's audio should match Ahmed, got {name_ahmed}"
    assert name_sarah == "Sarah", f"Sarah's audio should match Sarah, got {name_sarah}"
    assert dist_ahmed <= 0.10, f"Ahmed's distance should be <= 0.10, got {dist_ahmed}"
    assert dist_sarah <= 0.10, f"Sarah's distance should be <= 0.10, got {dist_sarah}"


@pytest.mark.asyncio
async def test_phase8_21_no_profiles_returns_no_match(db_session, test_audio_file):
    """
    E2E Test: Matching with no profiles returns no_match.
    Verifies:
    - Empty profile list returns None name
    - Confidence is 'no_match'
    """
    import uuid
    from datetime import datetime
    from app.models.client import Client
    
    embedding_service = SpeakerEmbeddingService()
    await embedding_service.initialize()

    if not embedding_service.is_available:
        pytest.skip("SpeakerEmbeddingService not available")

    profile_service = SpeakerProfileService(db_session)

    # Create a test client
    client = Client(
        id=str(uuid.uuid4()),
        company_name=f"Test Company {uuid.uuid4().hex[:6]}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        created_at=datetime.utcnow(),
    )
    db_session.add(client)
    await db_session.flush()

    embedding = await embedding_service.extract_embedding(test_audio_file)
    assert embedding is not None

    name, distance, confidence = await profile_service.match_speaker(
        client_id=client.id,
        embedding=embedding,
    )

    assert name is None
    assert confidence == "no_match"
    assert distance == 1.0
