import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_user
from backend.app.models.user import User
from backend.app.schemas.transcription import (
    TranscriptionCreate, TranscriptionUpdate, TranscriptionResponse,
    TranscriptionStatusResponse
)
from backend.app.services.transcription_service import transcription_service
from backend.app.services.audit_service import AuditService
from backend.app.schemas.audit import AuditLogCreate

logger = logging.getLogger(__name__)

router = APIRouter()
audit_service = AuditService()

@router.post("/", response_model=TranscriptionResponse, status_code=status.HTTP_201_CREATED)
async def start_transcription_endpoint(
    transcription_create: TranscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Starts a new transcription job for a given recording.
    """
    logger.info(f"User {current_user.id} starting transcription for recording {transcription_create.recording_id}")
    try:
        transcription = await transcription_service.start_transcription(
            db=db,
            recording_id=transcription_create.recording_id,
            current_user_id=current_user.id,
            language=transcription_create.language,
            enable_diarization=transcription_create.enable_diarization
        )
        await audit_service.create_audit_log(
            db=db,
            user_id=current_user.id,
            event_type="START_TRANSCRIPTION",
            resource_type="transcription",
            resource_id=transcription.id,
            details=f"Transcription job started for recording {transcription_create.recording_id}"
        )
        return transcription
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error starting transcription for recording {transcription_create.recording_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to start transcription")

@router.get("/", response_model=List[TranscriptionResponse])
async def get_transcriptions_endpoint(
    meeting_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves transcriptions. Currently supports filtering by meeting_id.
    """
    if meeting_id:
        logger.info(f"User {current_user.id} retrieving transcriptions for meeting {meeting_id}")
        transcriptions = await transcription_service.get_transcriptions_by_meeting(db, meeting_id, current_user.id)
        return transcriptions
    else:
        # TODO: Implement generic list with pagination if needed
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="meeting_id query parameter is required")

@router.get("/{id}", response_model=TranscriptionResponse)
async def get_transcription_endpoint(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves a transcription by its ID.
    """
    logger.info(f"User {current_user.id} retrieving transcription {id}")
    transcription = await transcription_service.get_transcription_by_id(db, id, current_user.id)
    return transcription

@router.patch("/{id}", response_model=TranscriptionResponse)
async def update_transcription_endpoint(
    id: int,
    transcription_update: TranscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually updates an existing transcription.
    """
    logger.info(f"User {current_user.id} updating transcription {id}")
    transcription = await transcription_service.update_transcription(db, id, transcription_update, current_user.id)
    await audit_service.create_audit_log(
        db=db,
        user_id=current_user.id,
        event_type="UPDATE_TRANSCRIPTION",
        resource_type="transcription",
        resource_id=transcription.id,
        details=f"Transcription {id} manually updated"
    )
    return transcription

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transcription_endpoint(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Deletes a transcription by its ID.
    """
    logger.info(f"User {current_user.id} deleting transcription {id}")
    await transcription_service.delete_transcription(db, id, current_user.id)
    await audit_service.create_audit_log(
        db=db,
        user_id=current_user.id,
        event_type="DELETE_TRANSCRIPTION",
        resource_type="transcription",
        resource_id=id,
        details=f"Transcription {id} deleted"
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/{id}/export", response_class=Response)
async def export_transcription_endpoint(
    id: int,
    format: str, # e.g., "txt", "docx", "pdf", "srt", "vtt"
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Exports a transcription in a specified format (TXT, DOCX, PDF, SRT, VTT).
    """
    logger.info(f"User {current_user.id} exporting transcription {id} in {format} format")
    transcription = await transcription_service.get_transcription_by_id(db, id, current_user.id)
    
    if format in ["txt", "srt", "vtt", "json"]:
        content = transcription_service.format_transcription(transcription, format)
        media_type = {
            "txt": "text/plain",
            "srt": "application/x-subrip",
            "vtt": "text/vtt",
            "json": "application/json"
        }.get(format, "application/octet-stream")
        filename = f"transcription_{id}.{format}"
        return Response(content=content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})
    elif format in ["docx", "pdf"]:
        content_bytes = transcription_service.export_transcription(transcription, format)
        media_type = {
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pdf": "application/pdf"
        }.get(format, "application/octet-stream")
        filename = f"transcription_{id}.{format}"
        return Response(content=content_bytes, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported export format: {format}")

@router.get("/{id}/status", response_model=TranscriptionStatusResponse)
async def get_transcription_status_endpoint(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the current status of a transcription job.
    """
    logger.info(f"User {current_user.id} retrieving status for transcription {id}")
    transcription = await transcription_service.get_transcription_by_id(db, id, current_user.id)
    return TranscriptionStatusResponse(
        id=transcription.id,
        status=transcription.status,
        message=f"Transcription status: {transcription.status.value}",
        failed_reason=transcription.failed_reason
    )