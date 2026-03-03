from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.api import deps
from app.models.user import User as UserModel
from app.schemas.recording import Recording, StreamStartResponse, StreamChunkResponse, StreamStopRequest
from app.services.recording_service import RecordingService

router = APIRouter()

@router.post("/upload/{meeting_id}", response_model=Recording)
async def upload_recording(
    meeting_id: str,
    file: UploadFile = File(...),
    recording_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Upload an audio recording for a specific meeting.
    """
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="File must be an audio recording")
    
    service = RecordingService(db)
    recording = await service.upload_recording(meeting_id, file, recording_id)
    
    # Reload with selectinload to avoid MissingGreenlet error during serialization
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.recording import Recording as RecordingModel
    result = await db.execute(
        select(RecordingModel).options(
            selectinload(RecordingModel.chunks)
        ).where(RecordingModel.id == recording.id)
    )
    return result.scalars().first()

@router.post("/stream/start/{meeting_id}", response_model=StreamStartResponse)
async def start_stream(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db)
):
    """Start a chunked audio stream upload."""
    service = RecordingService(db)
    result = await service.start_stream(meeting_id)
    return StreamStartResponse(**result)

@router.post("/stream/chunk", response_model=StreamChunkResponse)
async def upload_stream_chunk(
    upload_id: str = Form(...),
    file_key: str = Form(...),
    part_number: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db)
):
    """Upload a chunk to an active stream."""
    service = RecordingService(db)
    file_bytes = await file.read()
    etag = await service.upload_chunk(file_key, upload_id, part_number, file_bytes)
    return StreamChunkResponse(part_number=part_number, etag=etag)

@router.post("/stream/stop/{recording_id}", response_model=Recording)
async def stop_stream(
    recording_id: str,
    upload_id: str,
    file_key: str,
    request: StreamStopRequest,
    db: AsyncSession = Depends(deps.get_db)
):
    """Stop the stream and complete the upload."""
    service = RecordingService(db)
    parts = [{"PartNumber": p.PartNumber, "ETag": p.ETag} for p in request.parts]
    return await service.stop_stream(recording_id, file_key, upload_id, parts)

@router.get("/{recording_id}", response_model=Recording)
async def get_recording(
    recording_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user)
):
    """
    Get recording details by ID.
    """
    # Note: Implement get_recording in RecordingService if not exists
    pass
