from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.api import deps
from app.schemas.meeting import Meeting, MeetingCreate, MeetingUpdate
from app.models.meeting import Meeting as MeetingModel
from app.models.user import User as UserModel

router = APIRouter()

@router.get("/", response_model=List[Meeting])
def read_meetings(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve meetings.
    """
    meetings = db.query(MeetingModel).offset(skip).limit(limit).all()
    return meetings

@router.post("/", response_model=Meeting)
def create_meeting(
    *,
    db: Session = Depends(deps.get_db),
    meeting_in: MeetingCreate,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Create new meeting.
    """
    meeting = MeetingModel(
        id=str(uuid.uuid4()),
        title=meeting_in.title,
        description=meeting_in.description,
        location=meeting_in.location,
        start_time=meeting_in.start_time,
        end_time=meeting_in.end_time,
        status=meeting_in.status,
        creator_id=current_user.id
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting

@router.get("/{id}", response_model=Meeting)
def read_meeting(
    *,
    db: Session = Depends(deps.get_db),
    id: str,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Get meeting by ID.
    """
    meeting = db.query(MeetingModel).filter(MeetingModel.id == id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting

@router.put("/{id}", response_model=Meeting)
def update_meeting(
    *,
    db: Session = Depends(deps.get_db),
    id: str,
    meeting_in: MeetingUpdate,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Update a meeting.
    """
    meeting = db.query(MeetingModel).filter(MeetingModel.id == id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    update_data = meeting_in.dict(exclude_unset=True)
    for field in update_data:
        setattr(meeting, field, update_data[field])
    
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting