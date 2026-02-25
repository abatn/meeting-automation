<<<<<<< HEAD
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from app.api import deps
from app.models.action import Action
from app.schemas.action import ActionRead as ActionSchema, ActionUpdate, ActionCreate
from app.services.action_service import ActionService

router = APIRouter()

@router.get("/", response_model=List[ActionSchema])
async def get_actions(
    status: Optional[str] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user)
):
    query = select(Action)
    if status:
        query = query.where(Action.status == status)
    
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/pending", response_model=List[ActionSchema])
async def get_pending_actions(
    db: AsyncSession = Depends(deps.get_db),
    # Authentication removed for n8n internal calls. 
    # In production, this should be protected by a static API Key or internal network check.
):
    """Specific endpoint for n8n to get all pending actions"""
    query = select(Action).where(Action.status == "pending")
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{action_id}", response_model=ActionSchema)
async def get_action(
    action_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user)
):
    result = await db.execute(select(Action).where(Action.id == action_id))
=======
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
>>>>>>> b4b03e9 (feat: implement missing API routes for actions, reports, transcriptions and pv)
    action = result.scalars().first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action

<<<<<<< HEAD
@router.patch("/{action_id}", response_model=ActionSchema)
async def update_action(
    action_id: int,
    action_in: ActionUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user)
):
    action_service = ActionService(db)
    if action_in.status:
        action = await action_service.update_action_status(action_id, action_in.status)
    
    if action_in.assignee_id:
        action = await action_service.assign_action(action_id, action_in.assignee_id)
        
    # Handle other updates if needed
    if not action_in.status and not action_in.assignee_id:
        result = await db.execute(select(Action).where(Action.id == action_id))
        action = result.scalars().first()
        if action:
            for var, value in action_in.model_dump(exclude_unset=True).items():
                setattr(action, var, value)
            await db.commit()
            await db.refresh(action)
            
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
=======
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
>>>>>>> b4b03e9 (feat: implement missing API routes for actions, reports, transcriptions and pv)
    return action