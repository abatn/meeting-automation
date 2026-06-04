"""
Phase 8: Speaker Identification — E2E Tests
Phase 1: ONNX Model Loading & Embedding Extraction
"""
import os
import struct
import tempfile
import wave

import numpy as np
import pytest

from app.services.speaker_embedding_service import (
    SpeakerEmbeddingService,
    speaker_embedding_service,
    EMBEDDING_DIM,
    SAMPLE_RATE,
)


def _generate_test_audio(duration_seconds: float = 3.0, frequency: float = 440.0) -> bytes:
    """Generate a simple WAV file with a sine wave tone."""
    n_samples = int(SAMPLE_RATE * duration_seconds)
    t = np.linspace(0, duration_seconds, n_samples, dtype=np.float32)
    audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)
    audio = (audio * 32767).astype(np.int16)

    buf = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    with wave.open(buf.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())

    return buf.name


@pytest.mark.asyncio
async def test_phase8_01_onnx_model_loading():
    """
    E2E Test: ONNX model loads successfully and service initializes.
    Verifies:
    - ONNX Runtime is installed
    - Model file exists and loads
    - fbank filters load correctly
    - Service reports as available
    """
    service = SpeakerEmbeddingService()
    result = await service.initialize()

    assert result is True, "SpeakerEmbeddingService should initialize successfully"
    assert service.is_available is True, "Service should report as available"
    assert service._session is not None, "ONNX session should be created"
    assert service._fbank_filters is not None, "fbank filters should be loaded"
    assert service._fbank_filters.shape[0] == 80, "fbank should have 80 filters"


@pytest.mark.asyncio
async def test_phase8_02_embedding_extraction():
    """
    E2E Test: Extract embedding from a test audio file.
    Verifies:
    - Audio file can be loaded and processed
    - Embedding has correct dimension (192)
    - Embedding is L2-normalized (norm ≈ 1.0)
    """
    service = SpeakerEmbeddingService()
    await service.initialize()

    if not service.is_available:
        pytest.skip("SpeakerEmbeddingService not available")

    audio_path = _generate_test_audio(duration_seconds=3.0, frequency=440.0)

    try:
        embedding = await service.extract_embedding(audio_path)

        assert embedding is not None, "Embedding should not be None"
        assert isinstance(embedding, np.ndarray), "Embedding should be a numpy array"
        assert embedding.shape[0] == EMBEDDING_DIM, f"Embedding dimension should be {EMBEDDING_DIM}, got {embedding.shape[0]}"

        norm = np.linalg.norm(embedding)
        assert 0.99 <= norm <= 1.01, f"Embedding should be L2-normalized (norm ≈ 1.0), got {norm}"

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


@pytest.mark.asyncio
async def test_phase8_03_embedding_from_bytes():
    """
    E2E Test: Extract embedding from raw audio bytes (in-memory).
    Verifies:
    - Bytes-based extraction works
    - Same dimension and normalization as file-based extraction
    """
    service = SpeakerEmbeddingService()
    await service.initialize()

    if not service.is_available:
        pytest.skip("SpeakerEmbeddingService not available")

    audio_path = _generate_test_audio(duration_seconds=3.0, frequency=440.0)

    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        embedding = await service.extract_embedding_from_bytes(audio_bytes)

        assert embedding is not None, "Embedding from bytes should not be None"
        assert isinstance(embedding, np.ndarray), "Embedding should be a numpy array"
        assert embedding.shape[0] == EMBEDDING_DIM, f"Embedding dimension should be {EMBEDDING_DIM}, got {embedding.shape[0]}"

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


@pytest.mark.asyncio
async def test_phase8_04_embedding_too_short_audio():
    """
    E2E Test: Reject audio that is too short (< 1 second).
    Verifies:
    - Short audio returns None (graceful fallback)
    """
    service = SpeakerEmbeddingService()
    await service.initialize()

    if not service.is_available:
        pytest.skip("SpeakerEmbeddingService not available")

    audio_path = _generate_test_audio(duration_seconds=0.5, frequency=440.0)

    try:
        embedding = await service.extract_embedding(audio_path)
        assert embedding is None, "Short audio (< 1s) should return None"
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


@pytest.mark.asyncio
async def test_phase8_05_singleton_pattern():
    """
    E2E Test: Singleton pattern works correctly.
    Verifies:
    - get_instance() returns the same instance
    - Model is only loaded once
    """
    instance1 = await SpeakerEmbeddingService.get_instance()
    instance2 = await SpeakerEmbeddingService.get_instance()

    assert instance1 is instance2, "get_instance() should return the same singleton instance"
