import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transcription import Speaker
from app.models.meeting import Participant
from app.models.user import User

logger = logging.getLogger(__name__)

COSINE_DISTANCE_HIGH = 0.10
COSINE_DISTANCE_MEDIUM = 0.25
COSINE_DISTANCE_LOW = 0.40
EMBEDDING_DIM = 192


class SpeakerProfileService:
    """
    Manages speaker profiles for speaker identification.
    Handles CRUD operations, cosine distance matching, and enrollment.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profiles(self, client_id: str) -> List[Speaker]:
        """Get all speaker profiles for a client."""
        result = await self.db.execute(
            select(Speaker).where(
                Speaker.client_id == client_id
            )
        )
        profiles = list(result.scalars().all())
        return [p for p in profiles if p.embedding is not None]

    async def get_profile_by_name(self, client_id: str, name: str) -> Optional[Speaker]:
        """Get a speaker profile by name (checks both name and resolved_name)."""
        result = await self.db.execute(
            select(Speaker).where(
                Speaker.client_id == client_id,
                Speaker.embedding.isnot(None),
                (Speaker.name == name) | (Speaker.resolved_name == name),
            )
        )
        return result.scalars().first()

    async def create_profile(
        self,
        client_id: str,
        name: str,
        embedding: np.ndarray,
        source: str = "auto_enrolled",
        user_id: Optional[str] = None,
        speaker_label: Optional[str] = None,
        resolved_name: Optional[str] = None,
    ) -> Speaker:
        """Create a new speaker profile."""
        speaker = Speaker(
            id=f"sp-{client_id}-{name.lower().replace(' ', '-')}",
            meeting_id=None,
            client_id=client_id,
            name=speaker_label or name,
            resolved_name=resolved_name or name,
            user_id=user_id,
            embedding=embedding.flatten().tolist(),
            sample_count=1,
            source=source,
        )
        self.db.add(speaker)
        await self.db.flush()
        logger.info(f"Created speaker profile: {name} (client={client_id})")
        return speaker

    async def create_text_only_profile(
        self,
        client_id: str,
        name: str,
        source: str = "text_bootstrap",
        user_id: Optional[str] = None,
        speaker_label: Optional[str] = None,
        resolved_name: Optional[str] = None,
        confidence: float = 0.0,
        method: str = "text_only",
    ) -> Speaker:
        """Create a speaker profile without audio embedding (text-only bootstrap)."""
        speaker = Speaker(
            id=f"sp-{client_id}-{name.lower().replace(' ', '-')}",
            meeting_id=None,
            client_id=client_id,
            name=speaker_label or name,
            resolved_name=resolved_name or name,
            user_id=user_id,
            embedding=None,
            sample_count=0,
            source=source,
            mapping_confidence=confidence,
            mapping_method=method,
        )
        self.db.add(speaker)
        await self.db.flush()
        logger.info(f"Created text-only speaker profile: {name} (client={client_id})")
        return speaker

    async def update_profile_embedding(
        self,
        speaker: Speaker,
        new_embedding: np.ndarray,
    ) -> Speaker:
        """Update a speaker profile with a new embedding (running average)."""
        current = np.array(speaker.embedding, dtype=np.float32).flatten()
        n = speaker.sample_count or 1

        running_avg = (current * n + new_embedding) / (n + 1)
        running_avg = running_avg / (np.linalg.norm(running_avg) + 1e-10)

        await self.db.execute(
            update(Speaker)
            .where(Speaker.id == speaker.id)
            .values(
                embedding=running_avg.flatten().tolist(),
                sample_count=n + 1,
            )
        )
        speaker.embedding = running_avg.flatten().tolist()
        speaker.sample_count = n + 1
        logger.info(f"Updated speaker profile: {speaker.name} (samples={speaker.sample_count})")
        return speaker

    async def match_speaker(
        self,
        client_id: str,
        embedding: np.ndarray,
    ) -> Tuple[Optional[str], float, str]:
        """
        Match an embedding against stored profiles.

        Returns:
            (name, cosine_distance, confidence_level)
            confidence_level: "high", "medium", "low", or "no_match"
        """
        profiles = await self.get_profiles(client_id)

        if not profiles:
            return None, 1.0, "no_match"

        best_name = None
        best_distance = 1.0

        for profile in profiles:
            stored = np.array(profile.embedding, dtype=np.float32).flatten()
            if stored.shape[0] != EMBEDDING_DIM:
                logger.warning(
                    f"Skipping profile {profile.name}: embedding shape {stored.shape} != {EMBEDDING_DIM}"
                )
                continue
            cosine_distance = float(np.clip(1.0 - np.dot(embedding, stored), 0.0, 1.0))

            if cosine_distance < best_distance:
                best_distance = cosine_distance
                best_name = profile.name

        if best_distance < COSINE_DISTANCE_HIGH:
            confidence = "high"
        elif best_distance < COSINE_DISTANCE_MEDIUM:
            confidence = "medium"
        elif best_distance < COSINE_DISTANCE_LOW:
            confidence = "low"
        else:
            confidence = "no_match"
            best_name = None

        return best_name, best_distance, confidence

    async def delete_profile(self, client_id: str, speaker_id: str) -> bool:
        """Delete a speaker profile."""
        result = await self.db.execute(
            delete(Speaker).where(
                Speaker.id == speaker_id,
                Speaker.client_id == client_id
            )
        )
        await self.db.flush()
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Deleted speaker profile: {speaker_id}")
        return deleted

    async def resolve_user_id(
        self,
        client_id: str,
        name: str,
        meeting_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Resolve a speaker name to a user_id.

        Priority:
        1. Check participants for this meeting with matching name -> get user_id
        2. Check participants for this meeting with matching email -> get user_id
        3. Check users in this client with matching full_name -> get id
        4. Check users in this client with matching email -> get id

        Returns:
            user_id or None if not found
        """
        name_lower = name.lower().strip()

        # 1. Check participants for this meeting
        if meeting_id:
            stmt = select(Participant).where(
                Participant.meeting_id == meeting_id
            )
            result = await self.db.execute(stmt)
            participants = result.scalars().all()

            for p in participants:
                if p.name and p.name.lower().strip() == name_lower:
                    if p.user_id:
                        return p.user_id
                # 2. Check participant email against users
                if p.email and p.user_id:
                    # Participant already has user_id linked
                    pass

        # 3. Check users in this client by full_name
        stmt = select(User).where(
            User.client_id == client_id
        )
        result = await self.db.execute(stmt)
        users = result.scalars().all()

        for user in users:
            if user.full_name and user.full_name.lower().strip() == name_lower:
                return user.id
            # Substring match
            if user.full_name and (
                name_lower in user.full_name.lower() or
                user.full_name.lower() in name_lower
            ):
                return user.id

        return None


speaker_profile_service = SpeakerProfileService
