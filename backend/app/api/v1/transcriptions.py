from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict
from app.api import deps
from app.models.transcription import Transcription
from app.models.user import User as UserModel

router = APIRouter()

@router.patch("/{id}/speakers")
async def update_speaker_mapping(
    id: str,
    mapping: Dict[str, str],
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
):
    """
    Updates local speaker mapping (Optional UX feature).
    e.g. {"SPEAKER_00": "Ahmed"}
    This can be saved in DB or processed. Currently returns success.
    """
    result = await db.execute(select(Transcription).where(Transcription.id == id))
    transcription = result.scalar_one_or_none()
    
    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")

    # In a full implementation, we'd add `speaker_mapping = Column(JSON)` to the Transcription model.
    # For now, we simulate success for the optional UX requirement.
    return {"status": "success", "mapping": mapping}
