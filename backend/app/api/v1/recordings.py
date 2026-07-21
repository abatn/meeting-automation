from typing import Optional
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api import deps
from app.models.user import User as UserModel
from app.models.recording import Recording as RecordingModel
from app.models.meeting import Meeting as MeetingModel
from app.schemas.recording import (
    Recording,
    StreamStartResponse,
    StreamChunkResponse,
    StreamStopRequest,
)
from app.services.recording_service import RecordingService, StorageQuotaExceededError
from app.services.rate_limiter import check_recording_rate_limit, check_api_rate_limit, RateLimitExceededError

router = APIRouter()


@router.post("/upload/{meeting_id}", response_model=Recording)
async def upload_recording(
    meeting_id: str,
    file: UploadFile = File(...),
    recording_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
):
    """
    Upload an audio recording for a specific meeting.
    """
    if file.content_type is None or not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="File must be an audio recording")

    # Rate-Limit prüfen
    from app.models.client import Client
    from sqlalchemy import select as sel
    result = await db.execute(sel(Client).where(Client.id == current_user.client_id))
    client = result.scalar_one_or_none()
    plan = client.subscription_plan.value if client and client.subscription_plan else "GRATUIT"
    rate = check_recording_rate_limit(current_user.client_id, plan)
    if not rate["allowed"]:
        raise HTTPException(status_code=429, detail=f"Recording-Limit erreicht: {rate['limit']}/Tag. Upgrade auf PRO für mehr.")

    service = RecordingService(db)
    try:
        recording = await service.upload_recording(meeting_id, current_user.client_id, file, recording_id, user_id=current_user.id)
    except StorageQuotaExceededError as e:
        raise HTTPException(status_code=413, detail=str(e))

    # Reload with selectinload to avoid MissingGreenlet error during serialization
    result = await db.execute(
        select(RecordingModel)
        .options(selectinload(RecordingModel.chunks))
        .where(RecordingModel.id == recording.id)
        .where(RecordingModel.client_id == current_user.client_id)
    )
    return result.scalars().first()


@router.post("/stream/start/{meeting_id}", response_model=StreamStartResponse)
async def start_stream(
    meeting_id: str, 
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
):
    """Start a chunked audio stream upload. Only meeting creator can start recording."""
    result = await db.execute(
        select(MeetingModel)
        .where(MeetingModel.id == meeting_id)
        .where(MeetingModel.client_id == current_user.client_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only meeting creator can start recording")
    
    service = RecordingService(db)
    result = await service.start_stream(meeting_id, current_user.client_id)
    return StreamStartResponse(**result)


@router.post("/stream/chunk", response_model=StreamChunkResponse)
async def upload_stream_chunk(
    upload_id: str = Form(...),
    file_key: str = Form(...),
    part_number: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
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
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
):
    """Stop the stream and complete the upload. Only meeting creator can stop recording."""
    result = await db.execute(
        select(RecordingModel)
        .where(RecordingModel.id == recording_id)
        .where(RecordingModel.client_id == current_user.client_id)
    )
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    result = await db.execute(
        select(MeetingModel)
        .where(MeetingModel.id == recording.meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only meeting creator can stop recording")
    
    service = RecordingService(db)
    parts = [{"PartNumber": p.PartNumber, "ETag": p.ETag} for p in request.parts]
    try:
        return await service.stop_stream(recording_id, current_user.client_id, file_key, upload_id, parts)
    except StorageQuotaExceededError as e:
        raise HTTPException(status_code=413, detail=str(e))


@router.get("/{recording_id}", response_model=Recording)
async def get_recording(
    recording_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
):
    """
    Get recording details by ID.
    """
    result = await db.execute(
        select(RecordingModel)
        .options(selectinload(RecordingModel.chunks))
        .where(RecordingModel.id == recording_id)
        .where(RecordingModel.client_id == current_user.client_id)
    )
    recording = result.scalars().first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    return recording


@router.post("/presigned/upload/{meeting_id}")
async def get_presigned_upload_url(
    meeting_id: str,
    filename: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
):
    """
    Generate a presigned URL for direct frontend-to-MinIO upload.
    
    Returns:
        - presigned_url: URL for direct upload
        - file_key: S3/MinIO file key (client_id/recordings/{meeting_id}/{uuid}_{filename})
        - recording_id: Temporary recording_id for later reference
    """
    # Verify meeting exists and user has access
    result = await db.execute(
        select(MeetingModel)
        .where(MeetingModel.id == meeting_id)
        .where(MeetingModel.client_id == current_user.client_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Generate file key — bucket-per-tenant, no client_id in key
    file_key = f"recordings/{meeting_id}/{uuid.uuid4()}_{filename}"
    
    service = RecordingService(db)
    presigned_url = service.get_presigned_upload_url(file_key, current_user.client_id)
    
    from app.core.config import get_bucket_name
    return {
        "presigned_url": presigned_url,
        "file_key": file_key,
        "bucket": get_bucket_name(current_user.client_id),
    }


@router.post("/presigned/download/{recording_id}")
async def get_presigned_download_url(
    recording_id: str,
    expires_in: int = 3600,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
):
    """
    Generate a presigned URL for direct frontend-from-MinIO download.
    
    Returns:
        - presigned_url: URL for direct download
        - file_key: S3/MinIO file key
        - expires_in: URL expiry in seconds
    """
    # Verify recording exists and user has access
    result = await db.execute(
        select(RecordingModel)
        .where(RecordingModel.id == recording_id)
        .where(RecordingModel.client_id == current_user.client_id)
    )
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    service = RecordingService(db)
    presigned_url = service.get_presigned_download_url(recording.file_path, recording.client_id, expires_in)
    
    return {
        "presigned_url": presigned_url,
        "file_key": recording.file_path,
        "expires_in": expires_in,
    }
