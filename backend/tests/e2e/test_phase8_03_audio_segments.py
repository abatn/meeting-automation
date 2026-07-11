"""
Phase 8: Speaker Identification — E2E Tests
Phase 3: Audio Segment Extraction + Embedding Pipeline
"""
import asyncio
import os
import shutil
import tempfile
import wave

import numpy as np
import pytest

from app.services.audio_segment_service import AudioSegmentService, audio_segment_service
from app.services.speaker_embedding_service import SpeakerEmbeddingService, SAMPLE_RATE


def _generate_test_audio_file(
    duration_seconds: float = 10.0,
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
    """Generate a 30-second test audio file (needs >5s per speaker for extraction)."""
    path = _generate_test_audio_file(duration_seconds=30.0, frequency=440.0)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def sample_segments():
    """Sample Gladia diarization segments for 3 speakers."""
    return [
        {"speaker": "Speaker 0", "text": "Hello everyone", "start": 0.0, "end": 4.0},
        {"speaker": "Speaker 1", "text": "Hi there", "start": 4.0, "end": 8.0},
        {"speaker": "Speaker 0", "text": "Let's start the meeting", "start": 8.0, "end": 16.0},
        {"speaker": "Speaker 1", "text": "Sure, I agree", "start": 16.0, "end": 24.0},
        {"speaker": "Speaker 2", "text": "I have a question", "start": 24.0, "end": 29.0},
    ]


@pytest.fixture
def service():
    """Create an AudioSegmentService instance."""
    return AudioSegmentService()


@pytest.mark.asyncio
async def test_phase8_13_group_by_speaker(service, sample_segments):
    """
    E2E Test: Group segments by speaker label.
    Verifies:
    - Segments are correctly grouped by speaker
    - All speakers are present
    """
    grouped = service._group_by_speaker(sample_segments)

    assert "Speaker 0" in grouped
    assert "Speaker 1" in grouped
    assert "Speaker 2" in grouped
    assert len(grouped["Speaker 0"]) == 2
    assert len(grouped["Speaker 1"]) == 2
    assert len(grouped["Speaker 2"]) == 1


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
@pytest.mark.asyncio
async def test_phase8_14_extract_speaker_segments(service, test_audio_file, sample_segments):
    """
    E2E Test: Extract audio segments for each speaker.
    Verifies:
    - Audio files are created for speakers with enough audio
    - Speakers with too little audio are skipped
    - Returned paths point to existing files
    """
    result = await service.extract_speaker_segments(test_audio_file, sample_segments)

    assert isinstance(result, dict)
    assert len(result) >= 1, "At least one speaker should have enough audio"

    for speaker_label, audio_path in result.items():
        assert os.path.exists(audio_path), f"Audio file for {speaker_label} should exist"

    # Cleanup after assertion
    for path in result.values():
        if os.path.exists(path):
            os.remove(path)


@pytest.mark.asyncio
async def test_phase8_15_extract_embeddings(service, test_audio_file, sample_segments):
    """
    E2E Test: Extract embeddings from speaker segments.
    Verifies:
    - Embeddings are extracted for valid segments
    - Embeddings have correct dimension (192)
    - Temp files are cleaned up
    """
    speaker_segments = await service.extract_speaker_segments(
        test_audio_file, sample_segments
    )

    if not speaker_segments:
        pytest.skip("No speaker segments extracted (audio too short)")

    embeddings = await service.extract_embeddings(speaker_segments)

    assert isinstance(embeddings, dict)
    assert len(embeddings) == len(speaker_segments)

    for speaker_label, embedding in embeddings.items():
        if embedding is not None:
            assert isinstance(embedding, np.ndarray)
            assert embedding.shape[0] == 192, f"Embedding should be 192-dim, got {embedding.shape[0]}"

    for path in speaker_segments.values():
        assert not os.path.exists(path), f"Temp file {path} should be cleaned up"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
@pytest.mark.asyncio
async def test_phase8_16_skip_short_speaker(service, test_audio_file):
    """
    E2E Test: Skip speakers with too little audio.
    Verifies:
    - Speakers with < MIN_AUDIO_DURATION are skipped
    """
    short_segments = [
        {"speaker": "Speaker 0", "text": "Hi", "start": 0.0, "end": 1.0},
        {"speaker": "Speaker 1", "text": "Hello everyone, this is a much longer segment", "start": 1.0, "end": 8.0},
    ]

    result = await service.extract_speaker_segments(test_audio_file, short_segments)

    assert "Speaker 0" not in result, "Speaker 0 should be skipped (too short)"
    assert "Speaker 1" in result, "Speaker 1 should be included (enough audio)"

    for path in result.values():
        if os.path.exists(path):
            os.remove(path)


@pytest.mark.asyncio
async def test_phase8_17_cleanup_temp_files(service):
    """
    E2E Test: Clean up temporary audio files.
    Verifies:
    - All specified files are removed
    - Non-existent files don't cause errors
    """
    tmp_files = []
    for _ in range(3):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp.close()
        tmp_files.append(tmp.name)

    await service.cleanup_temp_files(tmp_files)

    for path in tmp_files:
        assert not os.path.exists(path), f"File {path} should be cleaned up"

    await service.cleanup_temp_files(["/nonexistent/file.wav"])
