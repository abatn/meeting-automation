"""
AssigneeResolver: Professional assignee resolution service.

Separates speaker identification from assignee resolution.
Uses full participant list + phonetic matching + directory resolution.

Based on Microsoft Teams / Zoom / Google Meet architecture:
1. Speaker mappings (high confidence)
2. Meeting participant list (medium confidence)
3. Phonetic matching (lower confidence)
4. Fuzzy string matching (lowest confidence)
5. External assignment (no match)
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from difflib import SequenceMatcher

from app.services.phonetic_matcher import phonetic_match, phonetic_candidates

logger = logging.getLogger(__name__)

# Confidence thresholds
CONFIDENCE_SPEAKER_MAPPING = 0.95
CONFIDENCE_PARTICIPANT_EXACT = 0.75
CONFIDENCE_PHONETIC = 0.60
CONFIDENCE_FUZZY = 0.50
CONFIDENCE_AMBIGUOUS = 0.30

# Minimum confidence for auto-assignment
AUTO_ASSIGN_THRESHOLD = 0.50

# Known non-person tokens
INVALID_ASSIGNEES = {
    "n/a", "null", "none", "non défini", "undefined",
    "tbd", "tba", "gladia", "mistral", "sentinel",
    "ai", "assistant"
}


class AssigneeResolution:
    """Result of assignee resolution."""

    def __init__(
        self,
        user_id: Optional[str] = None,
        external_name: Optional[str] = None,
        external_email: Optional[str] = None,
        confidence: float = 0.0,
        matched_via: str = "unknown",
        is_ambiguous: bool = False,
        candidates: Optional[List[str]] = None,
    ):
        self.user_id = user_id
        self.external_name = external_name
        self.external_email = external_email
        self.confidence = confidence
        self.matched_via = matched_via
        self.is_ambiguous = is_ambiguous
        self.candidates = candidates or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "external_name": self.external_name,
            "external_email": self.external_email,
            "confidence": self.confidence,
            "matched_via": self.matched_via,
            "is_ambiguous": self.is_ambiguous,
            "candidates": self.candidates,
        }


class AssigneeResolver:
    """
    Resolves assignee names to user IDs or external assignments.

    Resolution order (Microsoft Teams approach):
    1. Speaker mappings (who was identified by voice)
    2. Meeting participant list (who attended)
    3. Phonetic matching (name variants)
    4. Fuzzy string matching
    5. External assignment (no match)
    """

    def __init__(
        self,
        speaker_mappings: Optional[List[Dict[str, Any]]] = None,
        participant_names: Optional[List[str]] = None,
        client_users: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Initialize resolver with available name sources.

        Args:
            speaker_mappings: List of {speaker_label, resolved_name, confidence, method}
            participant_names: List of meeting participant names
            client_users: List of {id, full_name, email} for all client users
        """
        self.speaker_mappings = speaker_mappings or []
        self.participant_names = participant_names or []
        self.client_users = client_users or []

        # Build lookup structures
        self._resolved_speakers: Dict[str, Dict[str, Any]] = {}
        for m in self.speaker_mappings:
            name = m.get("resolved_name")
            if name:
                self._resolved_speakers[name.lower()] = m

        self._participant_set = set(n.lower() for n in self.participant_names if n)
        self._user_by_name: Dict[str, Dict[str, Any]] = {}
        for u in self.client_users:
            if u.get("full_name"):
                self._user_by_name[u["full_name"].lower()] = u
            if u.get("email"):
                self._user_by_name[u["email"].lower()] = u

    def resolve(
        self,
        assignee_name: str,
        single_speaker: Optional[str] = None,
    ) -> AssigneeResolution:
        """
        Resolve an assignee name to a user or external assignment.

        Args:
            assignee_name: The name extracted from Mistral PV
            single_speaker: The single speaker name (for 1-speaker meetings)

        Returns:
            AssigneeResolution with user_id or external assignment
        """
        if not assignee_name:
            return AssigneeResolution()

        # Step 1: Reject known non-person tokens
        if assignee_name.lower().strip() in INVALID_ASSIGNEES:
            if single_speaker:
                return self._resolve_to_speaker(single_speaker, "invalid_token_fallback")
            return AssigneeResolution()

        # Step 2: Direct match against speaker mappings (highest priority)
        result = self._match_speaker_mapping(assignee_name)
        if result:
            return result

        # Step 3: Exact match against participant list
        result = self._match_participant_exact(assignee_name)
        if result:
            return result

        # Step 4: Phonetic matching against all candidates
        result = self._match_phonetic(assignee_name)
        if result:
            return result

        # Step 5: Fuzzy string matching
        result = self._match_fuzzy(assignee_name)
        if result:
            return result

        # Step 6: Single speaker fallback
        if single_speaker:
            return self._resolve_to_speaker(single_speaker, "single_speaker_fallback")

        # Step 7: No match → external assignment
        if '@' in assignee_name:
            return AssigneeResolution(
                external_email=assignee_name,
                confidence=CONFIDENCE_AMBIGUOUS,
                matched_via="external_email",
            )
        else:
            return AssigneeResolution(
                external_name=assignee_name,
                confidence=CONFIDENCE_AMBIGUOUS,
                matched_via="external_name",
            )

    def _match_speaker_mapping(self, assignee_name: str) -> Optional[AssigneeResolution]:
        """Match against resolved speaker mappings."""
        name_lower = assignee_name.lower()

        # Exact match
        if name_lower in self._resolved_speakers:
            mapping = self._resolved_speakers[name_lower]
            speaker_conf = mapping.get("confidence", 0.0)
            user_id = mapping.get("user_id")

            # If mapping has user_id, return immediately
            if user_id:
                return AssigneeResolution(
                    user_id=user_id,
                    confidence=CONFIDENCE_SPEAKER_MAPPING * speaker_conf,
                    matched_via="speaker_mapping",
                )

            # No user_id in mapping, try to find user by name
            user = self._user_by_name.get(name_lower)
            if user:
                return AssigneeResolution(
                    user_id=user["id"],
                    confidence=CONFIDENCE_SPEAKER_MAPPING * speaker_conf,
                    matched_via="speaker_mapping_with_user_lookup",
                )

            # No user found, return None to continue resolution
            return None

        # Phonetic match against speaker names
        speaker_names = list(self._resolved_speakers.keys())
        phonetic_matches = phonetic_candidates(assignee_name, speaker_names, threshold=0.60)
        if phonetic_matches:
            best_name, phonetic_score = phonetic_matches[0]
            mapping = self._resolved_speakers[best_name]
            user_id = mapping.get("user_id")

            if user_id:
                return AssigneeResolution(
                    user_id=user_id,
                    confidence=CONFIDENCE_PHONETIC * phonetic_score,
                    matched_via="speaker_phonetic",
                )

            # Try user lookup
            user = self._user_by_name.get(best_name.lower())
            if user:
                return AssigneeResolution(
                    user_id=user["id"],
                    confidence=CONFIDENCE_PHONETIC * phonetic_score,
                    matched_via="speaker_phonetic_with_user_lookup",
                )

        return None

    def _match_participant_exact(self, assignee_name: str) -> Optional[AssigneeResolution]:
        """Exact match against meeting participant list."""
        name_lower = assignee_name.lower()

        if name_lower in self._participant_set:
            # Find the user in client_users
            user = self._user_by_name.get(name_lower)
            if user:
                return AssigneeResolution(
                    user_id=user["id"],
                    confidence=CONFIDENCE_PARTICIPANT_EXACT,
                    matched_via="participant_exact",
                )
            else:
                # Participant exists but no user link
                return AssigneeResolution(
                    external_name=assignee_name,
                    confidence=CONFIDENCE_PARTICIPANT_EXACT,
                    matched_via="participant_no_user",
                )

        return None

    def _match_phonetic(self, assignee_name: str) -> Optional[AssigneeResolution]:
        """Phonetic matching against all candidates."""
        # Gather all candidate names
        all_candidates = []
        all_candidates.extend(self.participant_names)
        all_candidates.extend(self._resolved_speakers.keys())
        # Add user names
        for u in self.client_users:
            if u.get("full_name"):
                all_candidates.append(u["full_name"])

        # Remove duplicates (case-insensitive)
        seen = set()
        unique_candidates = []
        for name in all_candidates:
            name_lower = name.lower()
            if name_lower not in seen:
                seen.add(name_lower)
                unique_candidates.append(name)

        # Phonetic matching
        matches = phonetic_candidates(assignee_name, unique_candidates, threshold=0.60)
        if matches:
            best_name, phonetic_score = matches[0]

            # Check for ambiguity (multiple high-scoring matches)
            high_matches = [m for m in matches if m[1] >= 0.70]
            is_ambiguous = len(high_matches) > 1

            if is_ambiguous:
                return AssigneeResolution(
                    external_name=assignee_name,
                    confidence=CONFIDENCE_AMBIGUOUS,
                    matched_via="ambiguous_phonetic",
                    is_ambiguous=True,
                    candidates=[m[0] for m in high_matches],
                )

            # Find the user
            user = self._user_by_name.get(best_name.lower())
            if user:
                return AssigneeResolution(
                    user_id=user["id"],
                    confidence=CONFIDENCE_PHONETIC * phonetic_score,
                    matched_via="phonetic",
                )
            else:
                return AssigneeResolution(
                    external_name=best_name,
                    confidence=CONFIDENCE_PHONETIC * phonetic_score,
                    matched_via="phonetic_no_user",
                )

        return None

    def _match_fuzzy(self, assignee_name: str) -> Optional[AssigneeResolution]:
        """Fuzzy string matching against all candidates."""
        all_candidates = []
        all_candidates.extend(self.participant_names)
        for u in self.client_users:
            if u.get("full_name"):
                all_candidates.append(u["full_name"])
            if u.get("email"):
                all_candidates.append(u["email"])

        # Remove duplicates
        seen = set()
        unique_candidates = []
        for name in all_candidates:
            name_lower = name.lower()
            if name_lower not in seen:
                seen.add(name_lower)
                unique_candidates.append(name)

        best_match = None
        best_score = 0.0

        for candidate in unique_candidates:
            score = SequenceMatcher(None, assignee_name.lower(), candidate.lower()).ratio()
            if score > best_score:
                best_score = score
                best_match = candidate

        if best_score >= 0.50 and best_match:
            user = self._user_by_name.get(best_match.lower())
            if user:
                return AssigneeResolution(
                    user_id=user["id"],
                    confidence=CONFIDENCE_FUZZY * best_score,
                    matched_via="fuzzy",
                )
            else:
                return AssigneeResolution(
                    external_name=best_match,
                    confidence=CONFIDENCE_FUZZY * best_score,
                    matched_via="fuzzy_no_user",
                )

        return None

    def _resolve_to_speaker(self, speaker_name: str, matched_via: str) -> AssigneeResolution:
        """Resolve to the single speaker."""
        name_lower = speaker_name.lower()
        mapping = self._resolved_speakers.get(name_lower)
        user_id = mapping.get("user_id") if mapping else None

        return AssigneeResolution(
            user_id=user_id,
            confidence=0.80,
            matched_via=matched_via,
        )
