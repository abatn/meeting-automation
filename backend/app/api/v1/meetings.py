from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.models.meeting import Meeting as MeetingModel
from app.models.meeting import Participant as ParticipantModel
from app.models.user import User as UserModel
from app.models.user import UserRole, UserStatus
from app.schemas.meeting import Meeting, MeetingCreate, MeetingWithPV
from app.schemas.user import User
from app.services.meeting_service import MeetingService

router = APIRouter()


@router.get("/users", response_model=List[User])
async def list_client_users(
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all active users for the current client to populate the participant dropdown.
    """
    result = await db.execute(
        select(UserModel)
        .where(UserModel.client_id == current_user.client_id)
        .where(UserModel.status == UserStatus.ACTIVE.value)
    )
    return result.scalars().all()


@router.get("/", response_model=List[MeetingWithPV])
async def read_meetings(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve meetings.
    """
    result = await db.execute(
        select(MeetingModel)
        .where(MeetingModel.client_id == current_user.client_id)
        .options(
            selectinload(MeetingModel.participants), 
            selectinload(MeetingModel.agendas),
            selectinload(MeetingModel.pv)
        )
        .offset(skip)
        .limit(limit)
    )
    meetings = result.scalars().all()
    return meetings


@router.get("/my-meetings", response_model=List[MeetingWithPV])
async def list_my_meetings(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve a list of meetings the current user is a participant in.
    """
    result = await db.execute(
        select(MeetingModel)
        .where(MeetingModel.client_id == current_user.client_id)
        .options(
            selectinload(MeetingModel.participants), 
            selectinload(MeetingModel.agendas),
            selectinload(MeetingModel.pv)
        )
        .join(ParticipantModel, MeetingModel.id == ParticipantModel.meeting_id)
        .where(ParticipantModel.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    meetings = result.scalars().all()
    return meetings


@router.get("/team-meetings", response_model=List[MeetingWithPV])
async def list_team_meetings(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve a list of meetings where users managed by the current user are participants.
    Accessible only by managers.
    """
    if current_user.role != UserRole.MANAGER and current_user.role != UserRole.DG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough privileges to access team meetings",
        )

    managed_user_ids = [report.id for report in current_user.reports]

    if not managed_user_ids:
        return []  # No reports, no team meetings

    result = await db.execute(
        select(MeetingModel)
        .where(MeetingModel.client_id == current_user.client_id)
        .options(
            selectinload(MeetingModel.participants), 
            selectinload(MeetingModel.agendas),
            selectinload(MeetingModel.pv)
        )
        .join(ParticipantModel, MeetingModel.id == ParticipantModel.meeting_id)
        .where(ParticipantModel.user_id.in_(managed_user_ids))
        .offset(skip)
        .limit(limit)
    )
    meetings = result.scalars().all()
    return meetings


@router.post("/", response_model=Meeting, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    *,
    db: AsyncSession = Depends(deps.get_db),
    meeting_in: MeetingCreate,
    current_user: UserModel = Depends(deps.get_current_user),
    meeting_service: MeetingService = Depends(deps.get_meeting_service),
) -> Any:
    """
    Create new meeting.
    """
    meeting = await meeting_service.create_meeting(
        meeting_in=meeting_in, owner_id=current_user.id, client_id=current_user.client_id
    )
    return meeting


@router.get("/{meeting_id}", response_model=Meeting)
async def get_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
    meeting_service: MeetingService = Depends(deps.get_meeting_service),
) -> Any:
    """
    Get meeting by ID.
    """
    meeting = await meeting_service.get_meeting(meeting_id, current_user.client_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.patch("/{meeting_id}/cancel", response_model=Meeting)
async def cancel_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
    meeting_service: MeetingService = Depends(deps.get_meeting_service),
) -> Any:
    """
    Cancel a planned meeting (Soft Delete).
    """
    from app.schemas.meeting import MeetingUpdate
    from app.models.meeting import MeetingStatus
    
    meeting = await meeting_service.get_meeting(meeting_id, current_user.client_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
        
    if meeting.status != MeetingStatus.PLANNED:
        raise HTTPException(status_code=400, detail="Only planned meetings can be cancelled")

    update_data = MeetingUpdate(status=MeetingStatus.CANCELLED)
    updated_meeting = await meeting_service.update_meeting(meeting_id, current_user.client_id, update_data)
    
    return updated_meeting


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
    meeting_service: MeetingService = Depends(deps.get_meeting_service),
):
    """
    Delete a meeting.
    """
    success = await meeting_service.delete_meeting(meeting_id, current_user.client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Meeting not found")
