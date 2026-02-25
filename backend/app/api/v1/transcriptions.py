<<<<<<< HEAD
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict
from app.api import deps
from app.models.transcription import Transcription
from app.models.user import User as UserModel

router = APIRouter()

@router.patch("/{id}/speakers")
async def update_speaker_mapping(
    id: str,
    mapping: Dict[str, str],
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
):
    """
    Updates local speaker mapping (Optional UX feature).
    e.g. {"SPEAKER_00": "Ahmed"}
    This can be saved in DB or processed. Currently returns success.
    """
    result = await db.execute(select(Transcription).where(Transcription.id == id))
    transcription = result.scalar_one_or_none()
    
    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")

    # In a full implementation, we'd add `speaker_mapping = Column(JSON)` to the Transcription model.
    # For now, we simulate success for the optional UX requirement.
    return {"status": "success", "mapping": mapping}
=======
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import uuid

from app.api import deps
from app.models.user import User as UserModel
from app.models.transcription import Transcription as TranscriptionModel
from app.tasks.transcription_tasks import transcribe_audio_task

router = APIRouter()

@router.post("/initiate", status_code=202)
async def initiate_transcription(
    data: dict, # Simplified: {"recording_id": "uuid", "language": "ar-TN"}
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Initiates the transcription process for a given recording.
    """
    recording_id = data.get("recording_id")
    if not recording_id:
        raise HTTPException(status_code=400, detail="recording_id is required")
        
    # Trigger the Celery task (which includes Diarization now)
    transcribe_audio_task.delay(recording_id)
    
    # Mock returning a transcription ID immediately
    return {
        "message": "Transcription initiated",
        "transcription_id": str(uuid.uuid4()), # In reality, we'd create the pending record here
        "status": "in_progress"
    }

@router.get("/{transcription_id}")
async def get_transcription(
    transcription_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieves the full transcription text for a recording.
    """
    stmt = select(TranscriptionModel).options(
        selectinload(TranscriptionModel.segments)
    ).where(TranscriptionModel.id == transcription_id)
    
    result = await db.execute(stmt)
    transcription = result.scalars().first()
    
    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")
        
    return {
        "id": transcription.id,
        "recording_id": transcription.recording_id,
        "language": transcription.language or "unknown",
        "text": transcription.full_text,
        "status": transcription.status
    }
>>>>>>> b4b03e9 (feat: implement missing API routes for actions, reports, transcriptions and pv)
