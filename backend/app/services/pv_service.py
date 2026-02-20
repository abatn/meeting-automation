import httpx
import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.pv import PV
from app.models.meeting import Meeting
from app.models.transcription import Transcription
from app.core.config import settings

logger = logging.getLogger(__name__)

class PVService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_pv(self, meeting_id: int):
        """Meeting-Daten + Transkription an n8n/Mistral senden"""
        # Get meeting and transcription
        meeting_result = await self.db.execute(select(Meeting).where(Meeting.id == meeting_id))
        meeting = meeting_result.scalars().first()
        
        transcription_result = await self.db.execute(
            select(Transcription).where(Transcription.meeting_id == meeting_id)
        )
        transcription = transcription_result.scalars().first()

        if not meeting or not transcription:
            logger.error(f"Cannot generate PV: Missing meeting {meeting_id} or transcription")
            return None

        payload = {
            "event": "pv.generate",
            "meeting_id": meeting.id,
            "title": meeting.title,
            "transcription": transcription.content,
            "callback_url": f"{settings.BACKEND_CALLBACK_URL}/pv-generated"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(settings.N8N_WEBHOOK_URL, json=payload, timeout=10.0)
                response.raise_for_status()
                logger.info(f"n8n PV generation triggered for meeting {meeting_id}")
        except Exception as e:
            logger.error(f"Failed to trigger n8n PV generation: {e}")

    async def validate_pv(self, pv_id: int, validator_id: int):
        """DG/Admin Freigabe -> n8n-Webhook 'pv-validated'"""
        result = await self.db.execute(select(PV).where(PV.id == pv_id))
        pv = result.scalars().first()
        
        if not pv:
            return None

        pv.status = "validated"
        pv.validated_by = validator_id
        await self.db.commit()

        # Trigger n8n for actions extraction and notifications
        payload = {
            "event": "pv.validated",
            "pv_id": pv.id,
            "meeting_id": pv.meeting_id,
            "content": pv.content,
            "callback_url": f"{settings.BACKEND_CALLBACK_URL}/actions-extracted"
        }

        try:
            async with httpx.AsyncClient() as client:
                await client.post(settings.N8N_WEBHOOK_PV_VALIDATED, json=payload, timeout=5.0)
                logger.info(f"n8n pv-validated triggered for PV {pv_id}")
        except Exception as e:
            logger.error(f"Failed to trigger n8n pv-validated: {e}")

        return pv

    async def get_pv_pdf(self, pv_id: int) -> bytes:
        """Generiertes PDF ausgeben (Placeholder)"""
        # Logic to retrieve PDF from storage or generate via service
        return b""

    async def version_control(self, meeting_id: int) -> List[PV]:
        """Ältere PV-Versionen speichern"""
        result = await self.db.execute(
            select(PV).where(PV.meeting_id == meeting_id).order_by(PV.created_at.desc())
        )
        return result.scalars().all()