import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.api import deps
from app.services.action_service import ActionService
from app.models.transcription import Transcription
from app.models.recording import Recording
from app.models.pv import PV

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/transcription-complete")
@router.post("/n8n/transcription")
async def transcription_complete(
    data: dict,
    db: AsyncSession = Depends(deps.get_db),
    _authorized: bool = Depends(deps.verify_internal_api_key),
):
    """Whisper-Ergebnis empfangen"""
    recording_id = data.get("recording_id")
    content = data.get("transcription") or data.get("transcription_text")
    meeting_id = data.get("meeting_id")

    if not meeting_id or not content:
        raise HTTPException(status_code=400, detail="Missing data")

    # Save transcription
    transcription = Transcription(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        recording_id=recording_id,
        full_text=content,
        status="completed",
    )
    db.add(transcription)

    # Update recording status
    await db.execute(
        update(Recording)
        .where(Recording.id == recording_id)
        .values(status="transcribed")
    )

    await db.commit()
    logger.info(f"Transcription completed for recording {recording_id}")

    # Optional: Automatically trigger PV generation
    # await PVService.generate_pv(content)

    return {"status": "success"}


@router.post("/pv-generated")
async def pv_generated(
    data: dict,
    db: AsyncSession = Depends(deps.get_db),
    _authorized: bool = Depends(deps.verify_internal_api_key),
):
    """Mistral-PV empfangen"""
    meeting_id = data.get("meeting_id")
    content = data.get("pv_content")

    if not meeting_id or not content:
        raise HTTPException(status_code=400, detail="Missing data")

    pv = PV(meeting_id=meeting_id, content=content, status="draft")
    db.add(pv)
    await db.commit()
    logger.info(f"PV draft generated for meeting {meeting_id}")

    return {"status": "success"}


@router.post("/actions-extracted")
async def actions_extracted(
    data: dict,
    db: AsyncSession = Depends(deps.get_db),
    _authorized: bool = Depends(deps.verify_internal_api_key),
):
    """Action-Items empfangen"""
    pv_id = data.get("pv_id")
    actions_list = data.get("actions", [])

    if not pv_id:
        raise HTTPException(status_code=400, detail="Missing pv_id")

    action_service = ActionService(db)
    await action_service.extract_actions_from_pv(pv_id, actions_list)

    return {"status": "success"}
