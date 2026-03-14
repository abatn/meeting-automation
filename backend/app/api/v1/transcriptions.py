from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.models.user import User as UserModel
from app.models.transcription import Transcription as TranscriptionModel

router = APIRouter()


@router.post("/initiate", status_code=202)
async def initiate_transcription(
    data: dict,  # Simplified: {"recording_id": "uuid", "language": "ar-TN"}
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
    from app.tasks.transcription_tasks import process_recording
    process_recording.delay(recording_id)

    # Mock returning a transcription ID immediately
    return {
        "message": "Transcription initiated",
        "transcription_id": str(uuid.uuid4()),  # In reality, we'd create pending record
        "status": "in_progress",
    }


@router.get("/meeting/{meeting_id}")
async def get_transcription_by_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieves the transcription associated with a specific meeting.
    """
    stmt = select(TranscriptionModel).where(TranscriptionModel.meeting_id == meeting_id)
    result = await db.execute(stmt)
    transcription = result.scalars().first()
    if not transcription:
        raise HTTPException(
            status_code=404, detail="Transcription for meeting not found"
        )
    return {
        "id": transcription.id,
        "recording_id": transcription.recording_id,
        "meeting_id": transcription.meeting_id,
        "language": transcription.language or "unknown",
        "full_text": transcription.full_text,
        "segments": transcription.segments,
        "status": transcription.status,
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
    stmt = select(TranscriptionModel).where(TranscriptionModel.id == transcription_id)

    result = await db.execute(stmt)
    transcription = result.scalars().first()

    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")

    return {
        "id": transcription.id,
        "recording_id": transcription.recording_id,
        "language": transcription.language or "unknown",
        "text": transcription.full_text,
        "segments": transcription.segments,  # Hinzugefügt
        "status": transcription.status,
    }


@router.post("/webhook")
async def transcription_webhook(
    payload: dict,
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Callback endpoint for AI services (e.g. Whisper) to post results.
    """
    # Mock processing
    return {"status": "success", "message": "Transcription results received"}
