import logging
from typing import Optional

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.speaker_profile_service import SpeakerProfileService
from app.services.speaker_embedding_service import SpeakerEmbeddingService

logger = logging.getLogger(__name__)

AUTO_ENROLL_THRESHOLD = 0.70


class AutoEnrollmentService:
    """
    Phase 6: Automatic Speaker Enrollment.
    Handles:
    - Auto-enrollment when fusion confidence exceeds threshold
    - Running average updates for existing profiles
    - user_id linking to actual users
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.profile_service = SpeakerProfileService(db)

    async def enroll_or_update(
        self,
        client_id: str,
        speaker_label: str,
        resolved_name: str,
        embedding: np.ndarray,
        confidence: float,
        method: str,
        meeting_id: Optional[str] = None,
        candidates: Optional[list] = None,
    ) -> bool:
        """
        Enroll a new speaker or update existing profile based on fusion result.

        Args:
            client_id: Tenant ID
            speaker_label: Gladia speaker label (e.g., "Speaker 0")
            resolved_name: Resolved speaker name from fusion
            embedding: Audio embedding vector
            confidence: Fusion confidence score (0.0-1.0)
            method: Fusion method ("audio", "text_inference", "fusion")
            meeting_id: Meeting ID for user_id resolution
            candidates: Candidate list for validation

        Returns:
            True if enrollment/update succeeded, False otherwise
        """
        if not resolved_name or confidence < AUTO_ENROLL_THRESHOLD:
            logger.info(
                f"Skipping enrollment for {speaker_label}: "
                f"confidence {confidence:.2f} < threshold {AUTO_ENROLL_THRESHOLD}"
            )
            return False

        # Validate: name must be in candidates if provided
        if candidates and resolved_name not in candidates:
            logger.warning(
                f"Skipping enrollment: '{resolved_name}' not in candidates"
            )
            return False

        # Resolve user_id from participants/users
        user_id = await self.profile_service.resolve_user_id(
            client_id=client_id,
            name=resolved_name,
            meeting_id=meeting_id,
        )

        existing = await self.profile_service.get_profile_by_name(client_id, resolved_name)

        if existing:
            await self.profile_service.update_profile_embedding(existing, embedding)
            logger.info(
                f"Updated existing profile: {resolved_name} "
                f"(method={method}, confidence={confidence:.2f}, user_id={user_id})"
            )
            return True
        else:
            await self.profile_service.create_profile(
                client_id=client_id,
                name=resolved_name,
                embedding=embedding,
                source="auto_enrolled",
                user_id=user_id,
                speaker_label=speaker_label,
                resolved_name=resolved_name,
            )
            logger.info(
                f"Auto-enrolled new speaker: {resolved_name} "
                f"(from {speaker_label}, method={method}, confidence={confidence:.2f}, user_id={user_id})"
            )
            return True

    async def enroll_text_only(
        self,
        client_id: str,
        speaker_label: str,
        resolved_name: str,
        confidence: float,
        method: str,
        meeting_id: Optional[str] = None,
        candidates: Optional[list] = None,
    ) -> bool:
        """
        Enroll a speaker without audio embedding (text-only bootstrap).
        Profile will be updated with embedding on next meeting.

        Lower threshold than full enrollment since we lack audio verification.
        """
        TEXT_ONLY_THRESHOLD = 0.60

        if not resolved_name or confidence < TEXT_ONLY_THRESHOLD:
            logger.info(
                f"Skipping text-only enrollment for {speaker_label}: "
                f"confidence {confidence:.2f} < threshold {TEXT_ONLY_THRESHOLD}"
            )
            return False

        if candidates and resolved_name not in candidates:
            logger.warning(
                f"Skipping text-only enrollment: '{resolved_name}' not in candidates"
            )
            return False

        user_id = await self.profile_service.resolve_user_id(
            client_id=client_id,
            name=resolved_name,
            meeting_id=meeting_id,
        )

        existing = await self.profile_service.get_profile_by_name(client_id, resolved_name)

        if existing:
            logger.info(
                f"Text-only profile already exists: {resolved_name} "
                f"(user_id={user_id}, method={method})"
            )
            return True
        else:
            await self.profile_service.create_text_only_profile(
                client_id=client_id,
                name=resolved_name,
                source="text_bootstrap",
                user_id=user_id,
                speaker_label=speaker_label,
                resolved_name=resolved_name,
                confidence=confidence,
                method=method,
            )
            logger.info(
                f"Text-only enrolled new speaker: {resolved_name} "
                f"(from {speaker_label}, method={method}, confidence={confidence:.2f}, user_id={user_id})"
            )
            return True

    async def batch_enroll(
        self,
        client_id: str,
        speaker_mappings: list,
        meeting_id: Optional[str] = None,
        candidates: Optional[list] = None,
    ) -> int:
        """
        Enroll multiple speakers from a meeting transcription.

        Args:
            client_id: Tenant ID
            speaker_mappings: List of dicts with keys:
                - speaker_label: Gladia label
                - resolved_name: Resolved name
                - embedding: Audio embedding
                - confidence: Fusion confidence
                - method: Fusion method
            meeting_id: Meeting ID for user_id resolution
            candidates: Candidate list for validation

        Returns:
            Number of successful enrollments
        """
        enrolled_count = 0

        for mapping in speaker_mappings:
            success = await self.enroll_or_update(
                client_id=client_id,
                speaker_label=mapping["speaker_label"],
                resolved_name=mapping["resolved_name"],
                embedding=mapping["embedding"],
                confidence=mapping["confidence"],
                method=mapping["method"],
                meeting_id=meeting_id,
                candidates=candidates,
            )
            if success:
                enrolled_count += 1

        logger.info(f"Batch enrollment complete: {enrolled_count}/{len(speaker_mappings)} enrolled")
        return enrolled_count


auto_enrollment_service = AutoEnrollmentService
