from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated, List

from backend.app.api.deps import get_db, get_current_active_user, require_dg, require_admin
from backend.app.models.user import User
from backend.app.schemas.action import ActionCreate, ActionResponse, ActionUpdate
from backend.app.services.action_service import action_service
from backend.app.services.audit_service import AuditService
from backend.app.schemas.audit import AuditLogCreate

router = APIRouter()
audit_service = AuditService()

@router.post("/", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
async def create_action_endpoint(
    request: Request,
    action_create: ActionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Creates a new action item.
    """
    action = await action_service.create_action(db, action_create, current_user.id)
    await audit_service.log_action(
        db=db,
        action="CREATE_ACTION",
        user_id=current_user.id,
        details={"entity_type": "action", "entity_id": action.id, "message": f"Action {action.id} created"}
    )
    return action

@router.get("/{action_id}", response_model=ActionResponse)
async def get_action_endpoint(
    action_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Retrieves a single action item by ID.
    """
    action = await action_service.get_action_by_id(db, action_id, current_user.id)
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    return action

@router.get("/", response_model=List[ActionResponse])
async def get_all_actions_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieves all action items for the current user.
    """
    actions = await action_service.get_actions_for_user(db, current_user.id, skip, limit)
    return actions

@router.put("/{action_id}", response_model=ActionResponse)
async def update_action_endpoint(
    request: Request,
    action_id: int,
    action_update: ActionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Updates an existing action item.
    """
    action = await action_service.update_action(db, action_id, action_update, current_user.id)
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    await audit_service.log_action(
        db=db,
        action="UPDATE_ACTION",
        user_id=current_user.id,
        details={"entity_type": "action", "entity_id": action.id, "message": f"Action {action.id} updated"}
    )
    return action

@router.delete("/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action_endpoint(
    request: Request,
    action_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Deletes an action item.
    """
    success = await action_service.delete_action(db, action_id, current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    await audit_service.log_action(
        db=db,
        action="DELETE_ACTION",
        user_id=current_user.id,
        details={"entity_type": "action", "entity_id": action_id, "message": f"Action {action_id} deleted"}
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)