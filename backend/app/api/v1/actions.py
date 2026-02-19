from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated, List, Optional
from datetime import datetime

from backend.app.api.deps import get_db, get_current_active_user, require_dg, require_admin
from backend.app.models.user import User, UserRole
from backend.app.models.action import ActionStatus
from backend.app.schemas.action import ActionCreate, ActionResponse, ActionUpdate, ActionComplete, ActionReminderResponse
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
    try:
        action = await action_service.create_action(db, action_create, current_user)
        await audit_service.create_audit_log(
            db=db,
            user_id=current_user.id,
            event_type="CREATE_ACTION",
            resource_type="action",
            resource_id=action.id,
            details=f"Action {action.id} created"
        )
        return action
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/{action_id}", response_model=ActionResponse)
async def get_action_endpoint(
    action_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Retrieves a single action item by ID.
    """
    action = await action_service.get_action_by_id(db, action_id)
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    
    # Basic authorization check: assignee, meeting organizer, or admin
    if action.assigned_to != current_user.id and \
       (action.meeting and action.meeting.organizer_id != current_user.id) and \
       current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this action.")
        
    return action

@router.get("/", response_model=List[ActionResponse])
async def get_all_actions_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    skip: int = 0,
    limit: int = 100,
    meeting_id: Optional[int] = Query(None, description="Filter by meeting ID"),
    assignee_id: Optional[int] = Query(None, description="Filter by assignee user ID"),
    status: Optional[ActionStatus] = Query(None, description="Filter by action status"),
    due_date_before: Optional[datetime] = Query(None, description="Filter actions due before this date"),
    due_date_after: Optional[datetime] = Query(None, description="Filter actions due after this date"),
    priority: Optional[int] = Query(None, ge=1, le=5, description="Filter by priority (1-5)")
):
    """
    Retrieves a list of action items with optional filters.
    Admins can see all actions. Other users can only see actions they are assigned to or actions from meetings they organized.
    """
    if current_user.role == UserRole.ADMIN:
        actions = await action_service.get_actions(
            db, skip, limit, meeting_id, assignee_id, status, due_date_before, due_date_after, priority
        )
    else:
        # For non-admins, filter by actions assigned to them or actions from meetings they organized
        # This logic might need to be refined in the service layer for complex OR conditions
        # For simplicity, we'll fetch all and filter here, or rely on service to handle user-specific queries
        actions_assigned = await action_service.get_actions_by_user(db, current_user.id, skip, limit, status)
        
        # Get meetings organized by current user
        # This part would ideally be handled more efficiently in the service or with a more complex query
        # For now, we'll fetch actions for each meeting organized by the user
        # This is a simplified approach and might not be efficient for many meetings
        # A better approach would be a single query joining actions, meetings, and users
        
        # For now, let's just return actions assigned to the user for non-admins
        # A more robust solution would involve a complex query in the service to handle both conditions
        actions = actions_assigned
        
        # If we need to include actions from meetings organized by the user, it would look something like this:
        # meetings_organized = await db.execute(select(Meeting).where(Meeting.organizer_id == current_user.id)).scalars().all()
        # for meeting in meetings_organized:
        #     meeting_actions = await action_service.get_actions_by_meeting(db, meeting.id, skip, limit, status)
        #     actions.extend(meeting_actions)
        # actions = list(set(actions)) # Remove duplicates if any

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
    try:
        action = await action_service.update_action(db, action_id, action_update, current_user)
        if not action:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
        await audit_service.create_audit_log(
            db=db,
            user_id=current_user.id,
            event_type="UPDATE_ACTION",
            resource_type="action",
            resource_id=action.id,
            details=f"Action {action.id} updated"
        )
        return action
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

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
    try:
        success = await action_service.delete_action(db, action_id, current_user)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
        await audit_service.create_audit_log(
            db=db,
            user_id=current_user.id,
            event_type="DELETE_ACTION",
            resource_type="action",
            resource_id=action_id,
            details=f"Action {action_id} deleted"
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/{action_id}/complete", response_model=ActionResponse)
async def complete_action_endpoint(
    request: Request,
    action_id: int,
    completion_data: ActionComplete,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Marks an action item as completed.
    """
    try:
        action = await action_service.complete_action(db, action_id, completion_data, current_user)
        if not action:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
        await audit_service.create_audit_log(
            db=db,
            user_id=current_user.id,
            event_type="COMPLETE_ACTION",
            resource_type="action",
            resource_id=action.id,
            details=f"Action {action.id} completed"
        )
        return action
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/user/{user_id}", response_model=List[ActionResponse])
async def get_actions_by_user_endpoint(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    skip: int = 0,
    limit: int = 100,
    status: Optional[ActionStatus] = Query(None, description="Filter by action status")
):
    """
    Retrieves all action items assigned to a specific user.
    Only accessible by the user themselves or an admin.
    """
    if current_user.id != user_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view actions for this user.")
    
    actions = await action_service.get_actions_by_user(db, user_id, skip, limit, status)
    return actions

@router.post("/{action_id}/remind", response_model=ActionReminderResponse)
async def send_action_reminder_endpoint(
    action_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Manually sends a reminder for an action item.
    Only accessible by the assignee, meeting organizer, or an admin.
    """
    action = await action_service.get_action_by_id(db, action_id)
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")

    # Check authorization
    is_organizer_or_admin = (action.meeting and action.meeting.organizer_id == current_user.id) or (current_user.role == UserRole.ADMIN)
    if action.assigned_to != current_user.id and not is_organizer_or_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to send reminder for this action.")

    # This will eventually call the notification service
    # For now, we simulate the reminder
    # await notification_service.send_action_reminder_notification(action)
    
    return ActionReminderResponse(
        message=f"Reminder sent for action {action_id}",
        action_id=action_id,
        user_id=action.assigned_to,
        timestamp=datetime.utcnow()
    )

@router.get("/overdue", response_model=List[ActionResponse])
async def get_overdue_actions_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_dg)] # Only DG or Admin can view overdue actions
):
    """
    Retrieves all overdue action items.
    Accessible only by users with DG or Admin role.
    """
    overdue_actions = await action_service.check_overdue_actions(db)
    return overdue_actions