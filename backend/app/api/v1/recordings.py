from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.api import deps
from app.schemas.recording import Recording
from app.services.recording_service import RecordingService

router = APIRouter()

@router.post("/upload/{meeting_id}", response_model=Recording)
async def upload_recording(
    meeting_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Upload an audio recording for a specific meeting.
    """
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="File must be an audio recording")
    
    service = RecordingService(db)
    return await service.upload_recording(meeting_id, file)

@router.get("/{recording_id}", response_model=Recording)
async def get_recording(
    recording_id: str,
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Get recording details by ID.
    """
    # Note: Implement get_recording in RecordingService if not exists
    pass
