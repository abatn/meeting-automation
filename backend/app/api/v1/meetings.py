from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated, List, Optional
from datetime import datetime

from app.api import deps
from app.core.database import get_db
from app.models.user import User
from app.models.meeting import MeetingStatus
from app.schemas.meeting import MeetingCreate, MeetingUpdate, MeetingResponse
from app.services.meeting_service import (
    get_meetings, get_meeting_by_id, create_meeting,
    update_meeting, delete_meeting, change_meeting_status
)
from app.services.audit_service import log_action

router = APIRouter()

@router.get("/", response_model=List[MeetingResponse])
async def read_meetings(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[MeetingStatus] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None
):
    """Listet alle Meetings auf (mit Filtern)."""
    meetings = await get_meetings(
        db, skip=skip, limit=limit,
        status=status, from_date=from_date, to_date=to_date
    )
    return meetings

@router.post("/", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_new_meeting(
    request: Request,
    meeting_data: MeetingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """Erstellt ein neues Meeting."""
    meeting = await create_meeting(db, meeting_data, current_user.id)
    
    # Audit-Log
    await log_action(
        db=db,
        user_id=current_user.id,
        action="CREATE",
        resource_type="meeting",
        resource_id=meeting.id,
        details={"title": meeting.title, "date": str(meeting.date)},
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
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
    meeting = await get_meeting_by_id(db, meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found"
        )
    
    # Audit-Log
    await log_action(
        db=db,
        user_id=current_user.id,
        action="READ",
        resource_type="meeting",
        resource_id=meeting_id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
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
    meeting = await update_meeting(db, meeting_id, meeting_data, current_user.id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found or insufficient permissions"
        )
    
    # Audit-Log
    await log_action(
        db=db,
        user_id=current_user.id,
        action="UPDATE",
        resource_type="meeting",
        resource_id=meeting_id,
        details={"changes": meeting_data.dict(exclude_unset=True)},
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return meeting

@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_meeting(
    request: Request,
    meeting_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """Löscht ein Meeting."""
    deleted = await delete_meeting(db, meeting_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found or insufficient permissions"
        )
    
    # Audit-Log
    await log_action(
        db=db,
        user_id=current_user.id,
        action="DELETE",
        resource_type="meeting",
        resource_id=meeting_id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
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
    meeting = await change_meeting_status(db, meeting_id, status, current_user.id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found or insufficient permissions"
        )
    
    # Audit-Log
    await log_action(
        db=db,
        user_id=current_user.id,
        action="STATUS_CHANGE",
        resource_type="meeting",
        resource_id=meeting_id,
        details={"new_status": status.value},
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return meeting