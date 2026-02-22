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
    action = result.scalars().first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action

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
    return action