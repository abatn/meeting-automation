import httpx
import logging
import json
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.core.config import settings
from app.models.pv import PV

logger = logging.getLogger(__name__)


class PVService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    async def generate_pv(transcription_text: str) -> Dict[str, Any]:
        """
        Generates a Procès-Verbal (PV) from transcription text using Mistral.
        """
        try:
            headers = {
                "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                "Content-Type": "application/json",
            }
            system_content = """Du erstellst professionelle Procès-Verbaux (PV) aus
Meeting-Transkriptionen. Kontext: Maghreb/Tunesien (Sprachen: Arabisch,
Französisch, Englisch Mix/Code-Switching). Analysiere den Transkript
und erstelle eine strukturierte Zusammenfassung in FRANZÖSISCH oder ARABISCH.

Format: Einleitung, Diskussionspunkte, Entscheidungen, Action-Items.

Für JEDE Aufgabe (Action Item) bestimme:
1. PRIORITÄT (high/medium/low) basierend auf Dringlichkeit und Wichtigkeit.
2. BEGRÜNDUNG für die Priorität (kurz, 1 Satz, als 'priority_reason').
3. DEADLINE (im Format YYYY-MM-DD, falls erwähnt, sonst null).
4. VERANTWORTLICHER (Name oder Rolle, als 'assignee').

Antworte EXKLUSIV im strukturierten JSON Format."""

            payload = {
                "model": "mistral-large-latest",
                "messages": [
                    {"role": "system", "content": system_content},
                    {
                        "role": "user",
                        "content": f"Erstelle ein PV für folgende Transkription:\n\n{transcription_text}",
                    },
                ],
                "response_format": {"type": "json_object"},
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0,
                )
                response.raise_for_status()
                result = response.json()
                # Extract content from the first choice
                content_str = result["choices"][0]["message"]["content"]
                return json.loads(content_str)

        except Exception as e:
            logger.error(f"PV generation error: {e}")
            raise RuntimeError(f"Mistral API error during PV generation: {e}")

    async def validate_pv(self, pv_id: str, user_id: str) -> Optional[PV]:
        """Marks a PV as validated by a specific user."""
        stmt = select(PV).where(PV.id == pv_id)
        result = await self.db.execute(stmt)
        pv = result.scalar_one_or_none()

        if not pv:
            return None

        pv.is_validated = True
        pv.validated_by_id = user_id
        pv.validated_at = datetime.utcnow()
        pv.status = "published"

        await self.db.commit()
        await self.db.refresh(pv)

        # Optional: Trigger n8n notification for validation
        await self._notify_validation(pv)

        return pv

    async def _notify_validation(self, pv: PV):
        payload = {"event": "pv.validated", "pv_id": pv.id, "meeting_id": pv.meeting_id}
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    settings.N8N_WEBHOOK_PV_VALIDATED, json=payload, timeout=5.0
                )
        except Exception as e:
            logger.error(f"Failed to notify n8n about PV validation: {e}")
