from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.api import deps
from app.schemas.action import Action, ActionCreate, ActionUpdate
from app.models.action import Action as ActionModel
from app.models.user import User as UserModel

router = APIRouter()

@router.get("/", response_model=List[Action])
async def list_actions(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    meeting_id: Optional[str] = None,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve a list of action items, with optional filters.
    """
    stmt = select(ActionModel)
    
    # Optional filters
    if status:
        stmt = stmt.where(ActionModel.status == status)
    if meeting_id:
        stmt = stmt.where(ActionModel.meeting_id == meeting_id)
        
    # assigned_to filter would need a join with assignments if the schema models it that way, 
    # but based on API.md we assume a direct relationship or we filter by user's assigned actions.
    # For now we just return the base query filtered by meeting and status.
    
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    actions = result.scalars().all()
    return actions

@router.post("/", response_model=Action, status_code=201)
async def create_action(
    *,
    db: AsyncSession = Depends(deps.get_db),
    action_in: ActionCreate,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Manually creates a new action item.
    """
    action = ActionModel(
        id=str(uuid.uuid4()),
        title=action_in.title,
        description=action_in.description,
        status=action_in.status,
        due_date=action_in.due_date,
        priority=action_in.priority,
        meeting_id=action_in.meeting_id
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    
    # TODO: Create the assignment to the user_id (action_in.assigned_to) if provided
    
    return action

@router.get("/{action_id}", response_model=Action)
async def get_action(
    *,
    db: AsyncSession = Depends(deps.get_db),
    action_id: str,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieves details of a specific action item.
    """
    result = await db.execute(select(ActionModel).where(ActionModel.id == action_id))
    action = result.scalars().first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action

@router.patch("/{action_id}/status", response_model=Action)
async def update_action_status(
    *,
    db: AsyncSession = Depends(deps.get_db),
    action_id: str,
    status_update: dict, # Simplified for PATCH {"status": "completed"}
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Updates the status of an action item.
    """
    result = await db.execute(select(ActionModel).where(ActionModel.id == action_id))
    action = result.scalars().first()
    
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
        
    if "status" in status_update:
        action.status = status_update["status"]
        
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return action