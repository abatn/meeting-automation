import json
import pytest
from unittest.mock import AsyncMock, patch

from app.services.mistral_fusion_service import MistralFusionService


@pytest.fixture
def fusion_service():
    return MistralFusionService()


@pytest.mark.asyncio
async def test_phase8_22_fusion_high_audio_confidence(fusion_service):
    """
    E2E Test: Fusion prefers high-confidence audio match.
    Verifies:
    - Audio match with distance < 0.30 is preferred
    - Fusion returns correct name with high confidence
    """
    audio_matches = [
        {"name": "Ahmed", "distance": 0.12, "confidence": "high"},
        {"name": "Sarah", "distance": 0.65, "confidence": "low"},
    ]

    text_context = "I think we should proceed with the project as planned."

    with patch.object(fusion_service, "_call_mistral", new_callable=AsyncMock) as mock_mistral:
        mock_mistral.return_value = json.dumps({
            "name": "Ahmed",
            "confidence": 0.95,
            "reasoning": "Audio match is highly confident",
        })

        name, confidence, method = await fusion_service.fuse_speaker_mapping(
            speaker_label="Speaker 0",
            text_context=text_context,
            audio_matches=audio_matches,
            client_id="test-client-id",
        )

        assert name == "Ahmed"
        assert confidence == 0.95
        assert method == "fusion"


@pytest.mark.asyncio
async def test_phase8_23_fusion_resolves_ambiguous_audio(fusion_service):
    """
    E2E Test: Fusion resolves ambiguous audio matching using text context.
    Verifies:
    - When audio matches are close, text context breaks the tie
    - Correct speaker is identified from self-introduction
    """
    audio_matches = [
        {"name": "Ahmed", "distance": 0.45, "confidence": "medium"},
        {"name": "Sarah", "distance": 0.48, "confidence": "medium"},
    ]

    text_context = "Hi, I'm Sarah. Let me share my screen."

    with patch.object(fusion_service, "_call_mistral", new_callable=AsyncMock) as mock_mistral:
        mock_mistral.return_value = json.dumps({
            "name": "Sarah",
            "confidence": 0.85,
            "reasoning": "Speaker introduced herself as Sarah",
        })

        name, confidence, method = await fusion_service.fuse_speaker_mapping(
            speaker_label="Speaker 1",
            text_context=text_context,
            audio_matches=audio_matches,
            client_id="test-client-id",
        )

        assert name == "Sarah"
        assert confidence == 0.85
        assert method == "fusion"


@pytest.mark.asyncio
async def test_phase8_24_text_only_inference(fusion_service):
    """
    E2E Test: Text-only inference when no audio matches available.
    Verifies:
    - Falls back to text inference gracefully
    - Extracts name from self-introduction
    """
    text_context = "Hello everyone, my name is Ahmed and I'll lead this meeting."

    with patch.object(fusion_service, "_call_mistral", new_callable=AsyncMock) as mock_mistral:
        mock_mistral.return_value = json.dumps({
            "name": "Ahmed",
            "confidence": 0.80,
            "reasoning": "Speaker introduced themselves",
        })

        name, confidence, method = await fusion_service.fuse_speaker_mapping(
            speaker_label="Speaker 0",
            text_context=text_context,
            audio_matches=[],
            client_id="test-client-id",
        )

        assert name == "Ahmed"
        assert confidence == 0.80
        assert method == "text_inference"


@pytest.mark.asyncio
async def test_phase8_25_no_match_returns_none(fusion_service):
    """
    E2E Test: Returns no match when both audio and text are empty.
    Verifies:
    - Empty audio_matches + empty text → no_match
    - Graceful handling of missing data
    """
    name, confidence, method = await fusion_service.fuse_speaker_mapping(
        speaker_label="Speaker 0",
        text_context="",
        audio_matches=[],
        client_id="test-client-id",
    )

    assert name is None
    assert confidence == 0.0
    assert method == "no_match"


@pytest.mark.asyncio
async def test_phase8_26_fusion_fallback_to_audio(fusion_service):
    """
    E2E Test: Falls back to audio matching when Mistral fails.
    Verifies:
    - Network error → fallback to best audio match
    - High confidence audio match still returned
    """
    audio_matches = [
        {"name": "Ahmed", "distance": 0.15, "confidence": "high"},
    ]

    text_context = "Some context text."

    with patch.object(fusion_service, "_call_mistral", new_callable=AsyncMock) as mock_mistral:
        mock_mistral.side_effect = Exception("Network error")

        name, confidence, method = await fusion_service.fuse_speaker_mapping(
            speaker_label="Speaker 0",
            text_context=text_context,
            audio_matches=audio_matches,
            client_id="test-client-id",
        )

        assert name == "Ahmed"
        assert confidence == 0.9
        assert method == "audio"


@pytest.mark.asyncio
async def test_phase8_27_fusion_invalid_json_response(fusion_service):
    """
    E2E Test: Handles malformed JSON response from Mistral.
    Verifies:
    - Invalid JSON → fallback to audio
    - No crash on parsing errors
    """
    audio_matches = [
        {"name": "Sarah", "distance": 0.25, "confidence": "high"},
    ]

    text_context = "Context text."

    with patch.object(fusion_service, "_call_mistral", new_callable=AsyncMock) as mock_mistral:
        mock_mistral.return_value = "This is not valid JSON"

        name, confidence, method = await fusion_service.fuse_speaker_mapping(
            speaker_label="Speaker 1",
            text_context=text_context,
            audio_matches=audio_matches,
            client_id="test-client-id",
        )

        assert name == "Sarah"
        assert confidence == 0.9
        assert method == "audio"
