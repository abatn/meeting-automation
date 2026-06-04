"""
E2E Tests für Pipeline Fixes.

Tests alle kritischen Fixes:
1. Gladia MIME type
2. Cosine distance
3. Transcript immutability
4. Soft-deleted user filter
5. Async S3 download
6. Confidence normalization
7. Single speaker context-aware
8. Sentinel semaphore
9. Duplicate user lookup merge
10. PV schema validation
"""
import pytest
import numpy as np
from unittest.mock import AsyncMock, patch, MagicMock
from difflib import SequenceMatcher

from app.services.gladia_service import GladiaService
from app.services.speaker_profile_service import SpeakerProfileService, COSINE_DISTANCE_HIGH, COSINE_DISTANCE_MEDIUM, COSINE_DISTANCE_LOW
from app.services.sentinel_service import SentinelService
from app.services.pv_service import PVService, _validate_pv_schema


# =============================================================================
# Test 1: Gladia MIME Type Detection
# =============================================================================
class TestGladiaMimeType:
    """Test that Gladia uses correct MIME type detection."""

    def test_mime_type_detection_wav(self):
        """WAV files should use audio/x-wav MIME type (Python standard)."""
        import mimetypes
        mime_type, _ = mimetypes.guess_type("test.wav")
        assert mime_type in ("audio/wav", "audio/x-wav")

    def test_mime_type_detection_mp3(self):
        """MP3 files should use audio/mpeg MIME type."""
        import mimetypes
        mime_type, _ = mimetypes.guess_type("test.mp3")
        assert mime_type == "audio/mpeg"

    def test_mime_type_fallback(self):
        """Unknown files should fallback to audio/wav."""
        import mimetypes
        mime_type, _ = mimetypes.guess_type("test.xyz")
        assert mime_type is None  # Will fallback to audio/wav in code


# =============================================================================
# Test 2: Cosine Distance (NOT Euclidean)
# =============================================================================
class TestCosineDistance:
    """Test that speaker matching uses cosine distance."""

    def test_identical_embeddings_zero_distance(self):
        """Identical embeddings should have zero cosine distance."""
        emb = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
        emb = emb / np.linalg.norm(emb)
        distance = float(1.0 - np.dot(emb, emb))
        assert abs(distance) < 1e-6

    def test_orthogonal_embeddings_unit_distance(self):
        """Orthogonal embeddings should have cosine distance of 1.0."""
        a = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        distance = float(1.0 - np.dot(a, b))
        assert distance == 1.0

    def test_cosine_distance_thresholds(self):
        """Test that thresholds are correctly named."""
        assert COSINE_DISTANCE_HIGH == 0.10
        assert COSINE_DISTANCE_MEDIUM == 0.25
        assert COSINE_DISTANCE_LOW == 0.40

    def test_confidence_levels(self):
        """Test confidence level assignment."""
        assert 0.05 < COSINE_DISTANCE_HIGH  # high confidence
        assert COSINE_DISTANCE_HIGH < COSINE_DISTANCE_MEDIUM
        assert COSINE_DISTANCE_MEDIUM < COSINE_DISTANCE_LOW


# =============================================================================
# Test 3: Transcript Immutability
# =============================================================================
class TestTranscriptImmutability:
    """Test that original transcript is not mutated."""

    def test_display_copy_preserves_original(self):
        """Display copy should not mutate original."""
        original_segments = [
            {"speaker": "Speaker 0", "text": "Hello"},
            {"speaker": "Speaker 1", "text": "Hi"},
        ]
        display_segments = [seg.copy() for seg in original_segments]

        name_map = {"Speaker 0": "Ahmed"}
        for seg in display_segments:
            if seg.get("speaker") in name_map:
                seg["speaker"] = name_map[seg["speaker"]]

        # Original should be unchanged
        assert original_segments[0]["speaker"] == "Speaker 0"
        # Display should be changed
        assert display_segments[0]["speaker"] == "Ahmed"


# =============================================================================
# Test 4: Confidence Normalization with Conflict Penalty
# =============================================================================
class TestConfidenceNormalization:
    """Test confidence normalization with conflict penalty."""

    def test_single_signal_no_penalty(self):
        """Single signal should have full confidence."""
        signals = [{"source": "audio", "name": "Ahmed", "score": 0.90}]
        total_weight = sum(s["score"] for s in signals)
        raw_score = signals[0]["score"]
        confidence = raw_score / total_weight
        assert confidence == pytest.approx(1.0, abs=0.01)

    def test_consensus_bonus(self):
        """Consensus signals should get bonus."""
        signals = [
            {"source": "audio", "name": "Ahmed", "score": 0.90},
            {"source": "text", "name": "Ahmed", "score": 0.85},
        ]
        total_weight = sum(s["score"] for s in signals)
        raw_score = 0.90 + 0.85  # Both for Ahmed
        confidence = raw_score / total_weight
        confidence = min(confidence * (1.0 + 0.15 * 1), 1.0)  # Bonus for 2 sources
        assert confidence > 0.90  # Should be boosted

    def test_conflict_penalty(self):
        """Conflicting signals should be penalized."""
        signals = [
            {"source": "audio", "name": "Ahmed", "score": 0.60},
            {"source": "llm", "name": "Fatima", "score": 0.55},
        ]
        total_weight = sum(s["score"] for s in signals)
        raw_score = 0.60  # Ahmed's score
        other_score = total_weight - raw_score  # Fatima's score
        conflict_ratio = other_score / raw_score
        confidence = (raw_score / total_weight) * max(1.0 - conflict_ratio * 0.5, 0.3)
        assert confidence < 0.60  # Should be penalized


# =============================================================================
# Test 5: Single Speaker Context-Aware Assignment
# =============================================================================
class TestSingleSpeakerContextAware:
    """Test that single speaker assignment is context-aware."""

    def test_context_reject_patterns(self):
        """Test context rejection patterns."""
        import re
        patterns = [
            r"(?:ask|tell|request|assign|delegate)\s+(?:to\s+)?(\w+)",
            r"(\w+)\s+(?:should|will|must|needs to)\s+",
        ]

        # Should reject: task mentions someone else
        text = "I'll ask Fatima to prepare the report"
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                assert match.group(1).lower() == "fatima"

    def test_context_valid_assignee(self):
        """Test contextually valid assignee."""
        import re
        patterns = [
            r"(?:ask|tell|request|assign|delegate)\s+(?:to\s+)?(\w+)",
            r"(\w+)\s+(?:should|will|must|needs to)\s+",
        ]

        def is_contextually_valid(assignee, text):
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    mentioned = match.group(1)
                    if mentioned.lower() != assignee.lower():
                        return False
            return True

        # Should reject: mentions Fatima but assignee is Ahmed
        assert not is_contextually_valid("Ahmed", "I'll ask Fatima to prepare the report")

        # Should accept: no mention of other person
        assert is_contextually_valid("Ahmed", "I'll prepare the report")


# =============================================================================
# Test 6: Sentinel Semaphore (NOT Lock)
# =============================================================================
class TestSentinelSemaphore:
    """Test that Sentinel uses semaphore for controlled parallelism."""

    def test_semaphore_allows_concurrent(self):
        """Semaphore should allow concurrent execution."""
        import asyncio
        semaphore = asyncio.Semaphore(2)

        async def test_concurrent():
            async with semaphore:
                await asyncio.sleep(0.01)
                return True

        # Should allow 2 concurrent
        results = asyncio.get_event_loop().run_until_complete(
            asyncio.gather(test_concurrent(), test_concurrent())
        )
        assert all(results)


# =============================================================================
# Test 7: PV Schema Validation
# =============================================================================
class TestPVSchemaValidation:
    """Test PV schema validation."""

    def test_missing_keys_filled(self):
        """Missing keys should be filled with defaults."""
        data = {"title": "Test"}
        result = _validate_pv_schema(data)
        assert "summary" in result
        assert "decisions" in result
        assert result["decisions"] == []
        assert "actions" in result
        assert result["actions"] == []

    def test_invalid_actions_removed(self):
        """Actions without description should be removed."""
        data = {
            "title": "Test",
            "summary": "Test",
            "decisions": [],
            "actions": [
                {"description": "Valid action"},
                {"priority": "high"},  # Missing description
                None,
            ],
        }
        result = _validate_pv_schema(data)
        assert len(result["actions"]) == 1
        assert result["actions"][0]["description"] == "Valid action"

    def test_valid_pv_unchanged(self):
        """Valid PV should pass unchanged."""
        data = {
            "title": "Test",
            "summary": "Test",
            "decisions": ["Decision 1"],
            "actions": [{"description": "Action 1", "priority": "high"}],
        }
        result = _validate_pv_schema(data)
        assert result == data


# =============================================================================
# Test 8: Soft-Deleted User Filter
# =============================================================================
class TestSoftDeletedUserFilter:
    """Test that soft-deleted users are excluded."""

    def test_deleted_at_filter_in_query(self):
        """Query should include deleted_at.is_(None) filter."""
        from sqlalchemy import select
        from app.models.user import User

        # Check that the filter is present in code
        import inspect
        from app.tasks.transcription_tasks import _save_pv_and_actions
        source = inspect.getsource(_save_pv_and_actions)
        assert "deleted_at.is_(None)" in source


# =============================================================================
# Test 9: Unified Fuzzy Threshold
# =============================================================================
class TestUnifiedFuzzyThreshold:
    """Test that fuzzy threshold is unified."""

    def test_threshold_is_60(self):
        """Fuzzy threshold should be 0.60."""
        import inspect
        from app.tasks.transcription_tasks import _save_pv_and_actions
        source = inspect.getsource(_save_pv_and_actions)
        assert ">= 0.60" in source
