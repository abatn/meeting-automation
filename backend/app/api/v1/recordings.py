from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated, List, Optional
from datetime import datetime
import shutil

from app.api import deps
from app.core.database import get_db
from app.models.user import User
from app.schemas.recording import RecordingCreate, RecordingUpdate, RecordingResponse
from app.services.recording_service import (
    get_recordings, get_recording_by_id, create_recording,
    update_recording, delete_recording
)
from app.services.audit_service import log_action

router = APIRouter()

@router.get("/", response_model=List[RecordingResponse])
async def read_recordings(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    meeting_id: Optional[int] = None,
    uploader_id: Optional[int] = None
):
    """Listet alle Aufnahmen auf (mit Filtern)."""
    recordings = await get_recordings(
        db, skip=skip, limit=limit,
        meeting_id=meeting_id, uploader_id=uploader_id
    )
    return recordings

@router.post("/", response_model=RecordingResponse, status_code=status.HTTP_201_CREATED)
async def create_new_recording(
    request: Request,
    meeting_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)],
    file: UploadFile = File(...)
):
    """Erstellt eine neue Aufnahme."""
    # Hier müsste die Datei in einem Speicherdienst (z.B. S3, Azure Blob) gespeichert werden.
    # Für dieses Beispiel speichern wir sie temporär und simulieren eine URL.
    file_location = f"temp_uploads/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Simulierte URL und Dateigröße
    simulated_file_url = f"http://example.com/recordings/{file.filename}"
    file_size = file.size if file.size else 0 # Fallback if size is not provided by UploadFile
    
    recording_data = RecordingCreate(
        meeting_id=meeting_id,
        file_url=simulated_file_url,
        duration=0, # Dauer müsste extrahiert werden
        file_size=file_size
    )
    
    recording = await create_recording(db, recording_data, current_user.id)
    
    # Audit-Log
    await log_action(
        db=db,
        user_id=current_user.id,
        action="CREATE",
        resource_type="recording",
        resource_id=recording.id,
        details={"meeting_id": meeting_id, "file_name": file.filename},
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return recording

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
    await log_action(
        db=db,
        user_id=current_user.id,
        action="READ",
        resource_type="recording",
        resource_id=recording_id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return recording

@router.put("/{recording_id}", response_model=RecordingResponse)
async def update_existing_recording(
    request: Request,
    recording_id: int,
    recording_data: RecordingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """Aktualisiert eine Aufnahme."""
    recording = await update_recording(db, recording_id, recording_data, current_user.id)
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found or insufficient permissions"
        )
    
    # Audit-Log
    await log_action(
        db=db,
        user_id=current_user.id,
        action="UPDATE",
        resource_type="recording",
        resource_id=recording_id,
        details={"changes": recording_data.dict(exclude_unset=True)},
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return recording

@router.delete("/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_recording(
    request: Request,
    recording_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """Löscht eine Aufnahme."""
    deleted = await delete_recording(db, recording_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found or insufficient permissions"
        )
    
    # Audit-Log
    await log_action(
        db=db,
        user_id=current_user.id,
        action="DELETE",
        resource_type="recording",
        resource_id=recording_id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )