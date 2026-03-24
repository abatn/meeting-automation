import uuid
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.api import deps
from app.models.user import User as UserModel, UserRole
from app.models.meeting_room import MeetingRoom as MeetingRoomModel
from app.schemas.meeting_room import MeetingRoom, MeetingRoomCreate, MeetingRoomUpdate

router = APIRouter()

@router.get("/", response_model=List[MeetingRoom])
async def list_meeting_rooms(
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """List all meeting rooms for the client."""
    result = await db.execute(
        select(MeetingRoomModel).where(MeetingRoomModel.client_id == current_user.client_id).order_by(MeetingRoomModel.name)
    )
    return result.scalars().all()

@router.post("/", response_model=MeetingRoom)
async def create_meeting_room(
    room_in: MeetingRoomCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Create a new meeting room."""
    db_obj = MeetingRoomModel(
        id=str(uuid.uuid4()),
        client_id=current_user.client_id,
        **room_in.model_dump()
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

@router.patch("/{room_id}", response_model=MeetingRoom)
async def update_meeting_room(
    room_id: str,
    room_in: MeetingRoomUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Update a meeting room."""
    stmt = select(MeetingRoomModel).where(MeetingRoomModel.id == room_id, MeetingRoomModel.client_id == current_user.client_id)
    result = await db.execute(stmt)
    db_obj = result.scalar_one_or_none()
    
    if not db_obj:
        raise HTTPException(status_code=404, detail="Meeting room not found")
        
    update_data = room_in.model_dump(exclude_unset=True)
    for field in update_data:
        setattr(db_obj, field, update_data[field])
        
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

@router.delete("/{room_id}")
async def delete_meeting_room(
    room_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Delete a meeting room."""
    stmt = delete(MeetingRoomModel).where(MeetingRoomModel.id == room_id, MeetingRoomModel.client_id == current_user.client_id)
    result = await db.execute(stmt)
    await db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Meeting room not found")
    return {"status": "deleted"}
