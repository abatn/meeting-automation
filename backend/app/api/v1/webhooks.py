from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.api import deps
from app.services.recording_service import RecordingService
from app.services.pv_service import PVService
from app.services.action_service import ActionService
from app.models.transcription import Transcription

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/transcription-complete")
async def transcription_complete(
    data: dict,
    db: AsyncSession = Depends(deps.get_db)
):
    """Whisper-Ergebnis empfangen"""
    recording_id = data.get("recording_id")
    content = data.get("transcription")
    meeting_id = data.get("meeting_id")

    if not recording_id or not content:
        raise HTTPException(status_code=400, detail="Missing data")

    # Save transcription
    transcription = Transcription(
        meeting_id=meeting_id,
        content=content,
        status="completed"
    )
    db.add(transcription)
    
    # Update recording status
    from app.models.recording import Recording
    from sqlalchemy import update
    await db.execute(
        update(Recording).where(Recording.id == recording_id).values(status="transcribed")
    )
    
    await db.commit()
    logger.info(f"Transcription completed for recording {recording_id}")
    
    # Optional: Automatically trigger PV generation
    pv_service = PVService(db)
    await pv_service.generate_pv(meeting_id)
    
    return {"status": "success"}

@router.post("/pv-generated")
async def pv_generated(
    data: dict,
    db: AsyncSession = Depends(deps.get_db)
):
    """Mistral-PV empfangen"""
    meeting_id = data.get("meeting_id")
    content = data.get("pv_content")

    if not meeting_id or not content:
        raise HTTPException(status_code=400, detail="Missing data")

    from app.models.pv import PV
    pv = PV(
        meeting_id=meeting_id,
        content=content,
        status="draft"
    )
    db.add(pv)
    await db.commit()
    logger.info(f"PV draft generated for meeting {meeting_id}")
    
    return {"status": "success"}

@router.post("/actions-extracted")
async def actions_extracted(
    data: dict,
    db: AsyncSession = Depends(deps.get_db)
):
    """Action-Items empfangen"""
    pv_id = data.get("pv_id")
    actions_list = data.get("actions", [])

    if not pv_id:
        raise HTTPException(status_code=400, detail="Missing pv_id")

    action_service = ActionService(db)
    await action_service.extract_actions_from_pv(pv_id, actions_list)
    
    return {"status": "success"}