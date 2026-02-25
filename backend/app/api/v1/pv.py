from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import uuid

from app.api import deps
from app.models.user import User as UserModel
from app.models.pv import PV as PVModel
from app.models.action import Action as ActionModel
from app.services.pv_service import PVService

router = APIRouter()

@router.post("/generate", status_code=202)
async def initiate_pv_generation(
    data: dict, # {"transcription_id": "uuid"}
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Generates a PV (meeting minutes) from a transcription.
    """
    transcription_id = data.get("transcription_id")
    if not transcription_id:
        raise HTTPException(status_code=400, detail="transcription_id is required")
        
    # In a real scenario, we'd lookup the transcription to get the meeting_id.
    # For now, we mock the response to match the spec.
    return {
        "message": "PV generation initiated",
        "pv_id": str(uuid.uuid4()),
        "status": "in_progress"
    }

@router.get("/{pv_id}")
async def get_pv(
    pv_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieves the generated PV content.
    """
    stmt = select(PVModel).options(
        selectinload(PVModel.sections)
    ).where(PVModel.id == pv_id)
    
    result = await db.execute(stmt)
    pv = result.scalars().first()
    
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")
        
    # Mocking actions related to this meeting
    actions_result = await db.execute(select(ActionModel).where(ActionModel.meeting_id == pv.meeting_id))
    actions = actions_result.scalars().all()
    
    return {
        "id": pv.id,
        "meeting_id": pv.meeting_id,
        "content": pv.content_html,
        "status": pv.status,
        "actions": [
            {
                "id": a.id,
                "description": a.description,
                "assigned_to": "Mocked User" # Usually via relationship
            } for a in actions
        ]
    }

@router.post("/{pv_id}/validate")
async def validate_pv(
    pv_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Marks a PV as validated.
    """
    service = PVService(db)
    pv = await service.validate_pv(pv_id, current_user.id)
    
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")
        
    return {
        "message": "PV validated successfully",
        "status": pv.status
    }
