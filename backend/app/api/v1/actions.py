from typing import Any, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.schemas.action import Action, ActionCreate
from app.models.action import Action as ActionModel, Assignment as AssignmentModel
from app.models.user import User as UserModel, UserRole


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

    if assigned_to:
        stmt = stmt.join(
            AssignmentModel, ActionModel.id == AssignmentModel.action_id
        ).where(AssignmentModel.user_id == assigned_to)

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    actions = result.scalars().all()
    return actions


@router.get("/my-actions", response_model=List[Action])
async def list_my_actions(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve a list of action items assigned to the current user.
    """
    stmt = select(ActionModel).join(AssignmentModel).where(
        AssignmentModel.user_id == current_user.id
    )

    if status:
        stmt = stmt.where(ActionModel.status == status)

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    actions = result.scalars().all()
    return actions


@router.get("/team-actions", response_model=List[Action])
async def list_team_actions(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve a list of action items assigned to users managed by the current user.
    Accessible only by managers.
    """
    if current_user.role != UserRole.MANAGER and current_user.role != UserRole.DG:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Only managers can access team actions."
        )
    # Note: Implementation of filtering by managed users would go here
    return []


@router.get("/pending", response_model=List[Action])
async def get_pending_actions_for_automation(
    db: AsyncSession = Depends(deps.get_db),
    api_key_valid: bool = Depends(deps.verify_internal_api_key)
) -> Any:
    """
    Retrieve all pending action items for N8N automation.
    Protected by X-Internal-API-Key.
    """
    stmt = select(ActionModel).where(ActionModel.status == "pending")
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
    await db.flush()

    if action_in.assigned_to:
        assignment = AssignmentModel(
            id=str(uuid.uuid4()),
            action_id=action.id,
            user_id=action_in.assigned_to
        )
        db.add(assignment)

    await db.commit()
    await db.refresh(action)

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
    status_update: dict,  # Simplified for PATCH {"status": "completed"}
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
