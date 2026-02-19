from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated, List, Optional
from datetime import datetime

from backend.app.api import deps
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.models.meeting import MeetingStatus
from backend.app.schemas.meeting import MeetingCreate, MeetingUpdate, MeetingResponse
from backend.app.services.meeting_service import meeting_service
from backend.app.services.audit_service import AuditService
from backend.app.schemas.audit import AuditLogCreate

router = APIRouter()
audit_service = AuditService()

@router.get("/", response_model=List[MeetingResponse])
async def read_meetings(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[MeetingStatus] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    organizer_id: Optional[int] = None # Add organizer_id filter
):
    """Listet alle Meetings auf (mit Filtern)."""
    meetings = await meeting_service.get_meetings(
        db, skip=skip, limit=limit,
        status=status, from_date=from_date, to_date=to_date,
        organizer_id=organizer_id # Pass new filter to service
    )
    return meetings

@router.post("/", response_model=MeetingResponse, status_code=http_status.HTTP_201_CREATED)
async def create_new_meeting(
    request: Request,
    meeting_data: MeetingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """Erstellt ein neues Meeting."""
    meeting = await meeting_service.create_meeting(db, meeting_data, current_user.id)
    
    # Audit-Log
    await audit_service.log_action(
        db=db,
        log_data=AuditLogCreate(
            user_id=current_user.id,
            action="CREATE",
            method=request.method,
            path=request.url.path,
            resource_type="meeting",
            resource_id=meeting.id,
            details={"title": meeting.title, "date": str(meeting.date)},
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            status_code=http_status.HTTP_201_CREATED
        )
    )
    
    return meeting

@router.get("/{meeting_id}", response_model=MeetingResponse)
async def read_meeting(
    request: Request,
    meeting_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """Holt die Details eines Meetings."""
    meeting = await meeting_service.get_meeting_by_id(db, meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Meeting not found"
        )
    
    # Audit-Log
    await audit_service.log_action(
        db=db,
        log_data=AuditLogCreate(
            user_id=current_user.id,
            action="READ",
            method=request.method,
            path=request.url.path,
            resource_type="meeting",
            resource_id=meeting_id,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            status_code=http_status.HTTP_200_OK
        )
    )
    
    return meeting

@router.put("/{meeting_id}", response_model=MeetingResponse)
async def update_existing_meeting(
    request: Request,
    meeting_id: int,
    meeting_data: MeetingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """Aktualisiert ein Meeting."""
    meeting = await meeting_service.update_meeting(db, meeting_id, meeting_data, current_user.id)
    if not meeting:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Meeting not found or insufficient permissions"
        )
    
    # Audit-Log
    await audit_service.log_action(
        db=db,
        log_data=AuditLogCreate(
            user_id=current_user.id,
            action="UPDATE",
            method=request.method,
            path=request.url.path,
            resource_type="meeting",
            resource_id=meeting_id,
            details={"changes": meeting_data.dict(exclude_unset=True)},
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            status_code=http_status.HTTP_200_OK
        )
    )
    
    return meeting

@router.delete("/{meeting_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_existing_meeting(
    request: Request,
    meeting_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """Löscht ein Meeting."""
    deleted = await meeting_service.delete_meeting(db, meeting_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Meeting not found or insufficient permissions"
        )
    
    # Audit-Log
    await audit_service.log_action(
        db=db,
        log_data=AuditLogCreate(
            user_id=current_user.id,
            action="DELETE",
            method=request.method,
            path=request.url.path,
            resource_type="meeting",
            resource_id=meeting_id,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            status_code=http_status.HTTP_204_NO_CONTENT
        )
    )

@router.patch("/{meeting_id}/status", response_model=MeetingResponse)
async def update_meeting_status(
    request: Request,
    meeting_id: int,
    status: MeetingStatus,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """Ändert den Status eines Meetings."""
    meeting = await meeting_service.change_meeting_status(db, meeting_id, status, current_user.id)
    if not meeting:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Meeting not found or insufficient permissions"
        )
    
    # Audit-Log
    await audit_service.log_action(
        db=db,
        log_data=AuditLogCreate(
            user_id=current_user.id,
            action="STATUS_CHANGE",
            method=request.method,
            path=request.url.path,
            resource_type="meeting",
            resource_id=meeting_id,
            details={"new_status": status.value},
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            status_code=http_status.HTTP_200_OK
        )
    )
    
    return meeting
