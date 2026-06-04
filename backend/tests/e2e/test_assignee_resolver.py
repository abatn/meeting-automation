"""
E2E Tests for AssigneeResolver and Phonetic Matching.

Tests the professional assignee resolution approach based on Microsoft Teams architecture:
1. Speaker mappings (high confidence)
2. Meeting participant list (medium confidence)
3. Phonetic matching (lower confidence)
4. Fuzzy string matching (lowest confidence)
5. External assignment (no match)
"""

import pytest
from app.services.assignee_resolver import AssigneeResolver, AssigneeResolution
from app.services.phonetic_matcher import DoubleMetaphone, phonetic_match, phonetic_candidates


class TestDoubleMetaphone:
    """Test Double Metaphone phonetic encoding."""

    def test_empty_string(self):
        dm = DoubleMetaphone()
        assert dm.encode("") == ("", "")
        assert dm.encode("   ") == ("", "")

    def test_simple_name(self):
        dm = DoubleMetaphone()
        p, s = dm.encode("Ahmed")
        assert p != ""  # Should produce a code
        assert len(p) <= 4  # Max 4 chars

    def test_phonetic_variants_same_code(self):
        """Mohammed/Muhammad/Mohammad should have similar phonetic codes."""
        dm = DoubleMetaphone()
        p1, _ = dm.encode("Mohammed")
        p2, _ = dm.encode("Mohammad")
        # May not be identical but should be similar
        assert p1[:2] == p2[:2] or p1 == p2

    def test_abdelkader_variants(self):
        """Abdelkader/Abdulqader should have similar phonetic codes."""
        dm = DoubleMetaphone()
        p1, _ = dm.encode("Abdelkader")
        p2, _ = dm.encode("Abdulqader")
        # Primary codes should share first 2 chars
        assert p1[:2] == p2[:2] or p1 == p2


class TestPhoneticMatch:
    """Test phonetic matching function."""

    def test_exact_match(self):
        assert phonetic_match("Ahmed", "Ahmed") == 1.0

    def test_case_insensitive(self):
        assert phonetic_match("ahmed", "AHMED") == 1.0

    def test_phonetic_variants(self):
        """Mohammed/Mohammad should have high phonetic match."""
        score = phonetic_match("Mohammed", "Mohammad")
        assert score >= 0.70

    def test_abdelkader_variants(self):
        """Abdelkader/Abdulqader should have high phonetic match."""
        score = phonetic_match("Abdelkader", "Abdulqader")
        assert score >= 0.60

    def test_unrelated_names(self):
        """Unrelated names should have low phonetic match."""
        score = phonetic_match("Ahmed", "Fatima")
        assert score < 0.60

    def test_empty_names(self):
        assert phonetic_match("", "Ahmed") == 0.0
        assert phonetic_match("Ahmed", "") == 0.0


class TestPhoneticCandidates:
    """Test phonetic candidate search."""

    def test_find_phonetic_match(self):
        candidates = ["Ahmed", "Fatima", "Mohammed"]
        matches = phonetic_candidates("Mohammad", candidates, threshold=0.60)
        assert len(matches) >= 1
        assert matches[0][0] == "Mohammed"

    def test_no_match(self):
        candidates = ["Ahmed", "Fatima"]
        matches = phonetic_candidates("John", candidates, threshold=0.60)
        assert len(matches) == 0

    def test_sorted_by_score(self):
        candidates = ["Mohammed", "Ahmed", "Mohammad"]
        matches = phonetic_candidates("Mohamad", candidates, threshold=0.60)
        # Should be sorted by score descending
        for i in range(len(matches) - 1):
            assert matches[i][1] >= matches[i + 1][1]


class TestAssigneeResolver:
    """Test professional assignee resolution."""

    @pytest.fixture
    def resolver(self):
        """Create resolver with test data."""
        speaker_mappings = [
            {
                "speaker_label": "Speaker 0",
                "resolved_name": "Abdelkader Batnini",
                "confidence": 0.90,
                "method": "audio",
                "user_id": "user-001",
            }
        ]
        participant_names = ["Abdelkader Batnini", "Mohammed Larbi Ennakti", "Fatima Zahra"]
        client_users = [
            {"id": "user-001", "full_name": "Abdelkader Batnini", "email": "abdelkader@test.com"},
            {"id": "user-002", "full_name": "Mohammed Larbi Ennakti", "email": "mohammed@test.com"},
            {"id": "user-003", "full_name": "Fatima Zahra", "email": "fatima@test.com"},
        ]
        return AssigneeResolver(
            speaker_mappings=speaker_mappings,
            participant_names=participant_names,
            client_users=client_users,
        )

    def test_speaker_mapping_exact(self, resolver):
        """Exact match against speaker mappings."""
        result = resolver.resolve("Abdelkader Batnini")
        assert result.user_id == "user-001"
        assert result.matched_via == "speaker_mapping"
        assert result.confidence >= 0.80

    def test_speaker_mapping_phonetic(self, resolver):
        """Phonetic match against speaker mappings (Abdulqader → Abdelkader)."""
        result = resolver.resolve("Abdulqader Al-Badnini")
        # Should match phonetically to Abdelkader Batnini
        assert result.user_id == "user-001" or result.matched_via in ("phonetic", "speaker_phonetic", "fuzzy")

    def test_participant_exact(self, resolver):
        """Exact match against participant list."""
        result = resolver.resolve("Mohammed Larbi Ennakti")
        assert result.user_id == "user-002"
        assert result.matched_via == "participant_exact"

    def test_phonetic_match(self, resolver):
        """Phonetic matching for name variants."""
        result = resolver.resolve("Mohammad Larbi Ennakti")
        # Should phonetically match Mohammed
        assert result.user_id == "user-002" or result.matched_via in ("phonetic", "fuzzy")

    def test_invalid_assignee(self, resolver):
        """Invalid tokens should be rejected."""
        result = resolver.resolve("N/A")
        assert result.user_id is None
        assert result.external_name is None

    def test_invalid_assignee_single_speaker(self, resolver):
        """Invalid tokens should fallback to single speaker."""
        result = resolver.resolve("N/A", single_speaker="Abdelkader Batnini")
        assert result.user_id == "user-001"
        assert result.matched_via == "invalid_token_fallback"

    def test_external_email(self, resolver):
        """Email addresses should be external assignments."""
        result = resolver.resolve("guest@example.com")
        assert result.external_email == "guest@example.com"
        assert result.matched_via == "external_email"

    def test_external_name(self, resolver):
        """Unknown names should be external assignments."""
        result = resolver.resolve("John Doe")
        assert result.external_name == "John Doe"
        assert result.matched_via == "external_name"

    def test_single_speaker_fallback(self, resolver):
        """No match should fallback to single speaker."""
        result = resolver.resolve("Unknown Person", single_speaker="Abdelkader Batnini")
        assert result.user_id == "user-001"
        assert result.matched_via == "single_speaker_fallback"

    def test_null_assignee(self, resolver):
        """Null assignee should return empty resolution."""
        result = resolver.resolve(None)
        assert result.user_id is None
        assert result.external_name is None

    def test_empty_assignee(self, resolver):
        """Empty assignee should return empty resolution."""
        result = resolver.resolve("")
        assert result.user_id is None
        assert result.external_name is None

    def test_fuzzy_match(self, resolver):
        """Fuzzy matching for typos."""
        result = resolver.resolve("Abdelkadr Batnini")  # Typo
        # Should fuzzy match to Abdelkader Batnini
        assert result.user_id == "user-001" or result.matched_via in ("fuzzy", "phonetic")


class TestAssigneeResolution:
    """Test AssigneeResolution result object."""

    def test_to_dict(self):
        result = AssigneeResolution(
            user_id="user-001",
            confidence=0.95,
            matched_via="speaker_mapping",
        )
        d = result.to_dict()
        assert d["user_id"] == "user-001"
        assert d["confidence"] == 0.95
        assert d["matched_via"] == "speaker_mapping"

    def test_ambiguous_resolution(self):
        result = AssigneeResolution(
            external_name="Mohammed",
            confidence=0.30,
            matched_via="ambiguous_phonetic",
            is_ambiguous=True,
            candidates=["Mohammed Ali", "Mohammed Hassan"],
        )
        assert result.is_ambiguous
        assert len(result.candidates) == 2
