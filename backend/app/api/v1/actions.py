from typing import Any, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.schemas.action import Action, ActionCreate, ActionSuggestion, ActionPattern, ActionStatistics
from app.models.action import Action as ActionModel, Assignment as AssignmentModel, ActionSuggestion as ActionSuggestionModel
from app.models.user import User as UserModel, UserRole
from app.services.action_service import ActionService
from pydantic import BaseModel

router = APIRouter()

# --- Analytics Endpoints ---

@router.get("/patterns", response_model=List[ActionPattern])
async def get_action_patterns(
    limit: int = 5,
    lang: Optional[str] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.check_permissions([UserRole.DG, UserRole.MANAGER])),
) -> Any:
    """
    Returns patterns of pending actions (e.g., frequently delayed tasks).
    Restricted to DG and Manager roles.
    """
    service = ActionService(db)
    return await service.get_action_patterns(current_user.client_id, limit, target_language=lang)

@router.get("/statistics/recurring", response_model=List[ActionStatistics])
async def get_recurring_statistics(
    lang: Optional[str] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.check_permissions([UserRole.DG, UserRole.MANAGER])),
) -> Any:
    """
    Returns statistics on AI action suggestions per user.
    Restricted to DG and Manager roles.
    """
    service = ActionService(db)
    return await service.get_recurring_statistics(current_user.client_id, target_language=lang)

# --- Suggestion Endpoints ---

class FeedbackRequest(BaseModel):
    suggestion_id: str
    action: str # "accept" or "reject"

class TranslateSuggestionsRequest(BaseModel):
    suggestions: List[dict]
    target_language: str

@router.get("/suggestions/{meeting_id}", response_model=List[ActionSuggestion])
async def get_action_suggestions(
    meeting_id: str,
    lang: Optional[str] = "fr",
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Analyzes the transcription of a meeting using ML (Mistral) to suggest potential action items.
    Checks DB first. If suggestions exist in a different language, it translates them on-the-fly.
    """
    # 1. Check if we already have suggestions
    stmt = select(ActionSuggestionModel).where(
        ActionSuggestionModel.meeting_id == meeting_id
    ).where(
        ActionSuggestionModel.client_id == current_user.client_id
    )
    result = await db.execute(stmt)
    existing_suggestions = result.scalars().all()
    
    action_service = ActionService(db)

    if existing_suggestions:
        # Check if we need to translate based on the language field
        base_lang = lang.split('-')[0] if lang else "fr"
        
        # Convert to Pydantic schemas first to avoid in-place SQLAlchemy modifications
        from app.schemas.action import ActionSuggestion as ActionSuggestionSchema
        schemas = [ActionSuggestionSchema.model_validate(s) for s in existing_suggestions]

        if existing_suggestions[0].language != base_lang:
            suggestions_data = [
                {"id": s.id, "title": s.title, "description": s.description} 
                for s in existing_suggestions
            ]
            
            translated_data = await action_service.translate_suggestions(suggestions_data, base_lang)
            
            # Merge translated strings back into the schemas
            for i, s in enumerate(schemas):
                # Ensure we don't index out of bounds if translation returned fewer items
                if i < len(translated_data):
                    s.title = translated_data[i].get("title", s.title)
                    s.description = translated_data[i].get("description", s.description)
            
        return schemas

    # 3. If none exist, generate them initially in the target language
    suggestions = await action_service.generate_suggestions_from_transcription(
        meeting_id, current_user.client_id, target_language=lang
    )
    return suggestions

@router.post("/suggestions/learn")
async def learn_action_suggestion_feedback(
    feedback: FeedbackRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Receives user feedback (accept/reject) on an ML-suggested action item.
    In a fully realized ML system, this data would feed back into model fine-tuning.
    """
    if feedback.action not in ["accept", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'accept' or 'reject'")
        
    action_service = ActionService(db)
    await action_service.learn_from_feedback(
        feedback.suggestion_id, 
        current_user.client_id, 
        feedback.action,
        user_id=current_user.id
    )
    return {"status": "success", "message": "Feedback recorded successfully."}

@router.post("/suggestions/translate")
async def translate_action_suggestions(
    request: TranslateSuggestionsRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Translates a list of suggestions into the target language for the UI.
    """
    action_service = ActionService(db)
    translated = await action_service.translate_suggestions(request.suggestions, request.target_language)
    return translated


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
    stmt = select(ActionModel).where(ActionModel.client_id == current_user.client_id)

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
    Retrieve a list of action items for the current user's client.
    Previously this was restricted to user_id, but since AI actions are assigned by name,
    we show all client actions here to ensure visibility.
    """
    stmt = (
        select(ActionModel)
        .where(ActionModel.client_id == current_user.client_id)
    )

    if status:
        stmt = stmt.where(ActionModel.status == status)

    stmt = stmt.order_by(ActionModel.created_at.desc()).offset(skip).limit(limit)
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
            detail="Insufficient permissions. Only managers can access team actions.",
        )
    
    managed_user_ids = [report.id for report in current_user.reports]
    if not managed_user_ids:
        return []

    stmt = (
        select(ActionModel)
        .where(ActionModel.client_id == current_user.client_id)
        .join(AssignmentModel)
        .where(AssignmentModel.user_id.in_(managed_user_ids))
    )
    
    if status:
        stmt = stmt.where(ActionModel.status == status)

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/pending", response_model=List[ActionAutomation])
async def get_pending_actions_for_automation(
    db: AsyncSession = Depends(deps.get_db),
    api_key_valid: bool = Depends(deps.verify_internal_api_key),
) -> Any:
    """
    Retrieve all pending action items with enriched contact info for N8N automation.
    Protected by X-Internal-API-Key.
    """
    from sqlalchemy.orm import joinedload
    from app.models.user import User as UserModel
    
    # We join Action -> Assignment -> User (Assignee) and then find the Manager of that user
    stmt = (
        select(ActionModel)
        .where(ActionModel.status == "pending")
        .options(
            joinedload(ActionModel.assignments).joinedload(AssignmentModel.user)
        )
    )
    result = await db.execute(stmt)
    actions = result.scalars().unique().all()
    
    enriched_actions = []
    for action in actions:
        # Get primary assignee info
        assignee_name = None
        assignee_phone = None
        manager_email = None
        
        if action.assignments:
            user = action.assignments[0].user
            if user:
                assignee_name = user.full_name or user.email
                # Simulate phone logic if not in model, or use email as fallback
                assignee_phone = "Simulation_Phone" 
                
                # Fetch Manager Email
                if user.manager_id:
                    mgr_stmt = select(UserModel.email).where(UserModel.id == user.manager_id)
                    mgr_res = await db.execute(mgr_stmt)
                    manager_email = mgr_res.scalar()

        enriched_actions.append({
            "id": action.id,
            "title": action.title,
            "due_date": action.due_date,
            "assignee_name": assignee_name,
            "assignee_phone": assignee_phone,
            "manager_email": manager_email
        })
        
    return enriched_actions


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
        client_id=current_user.client_id,
        title=action_in.title,
        description=action_in.description,
        status=action_in.status,
        due_date=action_in.due_date,
        priority=action_in.priority,
        meeting_id=action_in.meeting_id,
    )
    db.add(action)
    await db.flush()

    if action_in.assigned_to:
        assignment = AssignmentModel(
            id=str(uuid.uuid4()), action_id=action.id, user_id=action_in.assigned_to
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
    result = await db.execute(
        select(ActionModel)
        .where(ActionModel.id == action_id)
        .where(ActionModel.client_id == current_user.client_id)
    )
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
    result = await db.execute(
        select(ActionModel)
        .where(ActionModel.id == action_id)
        .where(ActionModel.client_id == current_user.client_id)
    )
    action = result.scalars().first()

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    if "status" in status_update:
        action.status = status_update["status"]

    db.add(action)
    await db.commit()
    await db.refresh(action)
    return action
