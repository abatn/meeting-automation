from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated, List, Optional
from datetime import datetime
import shutil # Not needed anymore for direct file handling

from backend.app.api import deps
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.models.recording import RecordingStatus # Import RecordingStatus
from backend.app.schemas.recording import RecordingCreate, RecordingUpdate, RecordingResponse, RecordingUploadResponse
from backend.app.schemas.audit import AuditLogCreate
from backend.app.services.recording_service import (
    get_recording_by_id,
    get_recordings_by_meeting, # Use this for meeting-specific listings
    upload_recording, # New upload function
    update_recording_status, # New status update function
    delete_recording,
    get_recording_download_url
)
from backend.app.services.audit_service import AuditService

router = APIRouter()
audit_service = AuditService()

@router.post("/upload", response_model=RecordingUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_new_recording(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)],
    meeting_id: int = Query(..., description="The ID of the meeting this recording belongs to."),
    file: UploadFile = File(..., description="The audio file to upload (max 500MB, audio/*).")
):
    """
    Uploads a new audio recording for a specific meeting.
    The file will be validated, stored in S3/MinIO, and a database entry created.
    """
    try:
        recording = await upload_recording(
            db=db,
            meeting_id=meeting_id,
            uploader_id=current_user.id,
            file=file
        )
        
        # Audit-Log
        log_data = AuditLogCreate(
            user_id=current_user.id,
            action="UPLOAD",
            resource_type="recording",
            resource_id=recording.id,
            details={"meeting_id": meeting_id, "file_name": file.filename, "file_size": file.size},
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            method=request.method,
            path=request.url.path
        )
        await audit_service.log_action(db=db, log_data=log_data)
        
        return RecordingUploadResponse(
            id=recording.id,
            status=recording.status,
            message="Recording upload initiated successfully."
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during upload: {e}"
        )

@router.get("/meeting/{meeting_id}", response_model=List[RecordingResponse])
async def get_all_recordings_for_meeting(
    request: Request,
    meeting_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """Listet alle Aufnahmen für ein bestimmtes Meeting auf."""
    recordings = await get_recordings_by_meeting(db, meeting_id)
    
    # Audit-Log (optional, kann bei häufigen Abfragen zu viel werden)
    log_data = AuditLogCreate(
        user_id=current_user.id,
        action="READ_ALL_FOR_MEETING",
        resource_type="recording",
        resource_id=0, # No specific recording ID
        details={"meeting_id": meeting_id},
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        method=request.method,
        path=request.url.path
    )
    await audit_service.log_action(db=db, log_data=log_data)
    
    return recordings

@router.get("/{recording_id}", response_model=RecordingResponse)
async def read_recording(
    request: Request,
    recording_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """Holt die Details einer Aufnahme."""
    recording = await get_recording_by_id(db, recording_id)
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found"
        )
    
    # Audit-Log
    log_data = AuditLogCreate(
        user_id=current_user.id,
        action="READ",
        resource_type="recording",
        resource_id=recording_id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        method=request.method,
        path=request.url.path
    )
    await audit_service.log_action(db=db, log_data=log_data)
    
    return recording

@router.get("/{recording_id}/download")
async def download_recording(
    request: Request,
    recording_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """Generiert einen signierten Download-Link für eine Aufnahme."""
    download_url = await get_recording_download_url(db, recording_id, current_user.id)
    if not download_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found or not available for download."
        )
    
    # Audit-Log
    log_data = AuditLogCreate(
        user_id=current_user.id,
        action="DOWNLOAD",
        resource_type="recording",
        resource_id=recording_id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        method=request.method,
        path=request.url.path
    )
    await audit_service.log_action(db=db, log_data=log_data)
    
    return {"download_url": download_url}

@router.patch("/{recording_id}/status", response_model=RecordingResponse)
async def update_recording_status_endpoint(
    request: Request,
    recording_id: int,
    new_status: RecordingStatus,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """Aktualisiert den Status einer Aufnahme."""
    recording = await update_recording_status(db, recording_id, new_status, current_user.id)
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found or insufficient permissions"
        )
    
    # Audit-Log
    log_data = AuditLogCreate(
        user_id=current_user.id,
        action="UPDATE_STATUS",
        resource_type="recording",
        resource_id=recording_id,
        details={"new_status": new_status.value},
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        method=request.method,
        path=request.url.path
    )
    await audit_service.log_action(db=db, log_data=log_data)
    
    return recording

@router.delete("/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_recording(
    request: Request,
    recording_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """Löscht eine Aufnahme."""
    try:
        deleted = await delete_recording(db, recording_id, current_user.id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found or insufficient permissions"
            )
        
        # Audit-Log
        log_data = AuditLogCreate(
            user_id=current_user.id,
            action="DELETE",
            resource_type="recording",
            resource_id=recording_id,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            method=request.method,
            path=request.url.path
        )
        await audit_service.log_action(db=db, log_data=log_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during deletion: {e}"
        )

# Remove the old / and /{recording_id} endpoints if they are no longer needed
# The task specifies specific endpoints, so I'm replacing the generic ones.
# If a generic GET / is still desired, it needs to be re-implemented with proper filtering.