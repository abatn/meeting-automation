from typing import Optional
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from backend.app.api import deps
from backend.app.api.deps import get_current_user
from backend.app.models.user import User
from backend.app.schemas.pv import PVGenerate, PVUpdate, PVValidate, PVResponse, PVValidationResponse
from backend.app.services.pv_service import PVService
from backend.app.services.audit_service import AuditService, AuditAction
from backend.app.schemas.audit import AuditLogCreate

router = APIRouter()
audit_service = AuditService()

@router.post("/{meeting_id}/generate", response_model=PVResponse)
async def generate_pv(
    request: Request,
    meeting_id: int,
    pv_generate: PVGenerate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
):
    pv_service = PVService(db)
    pv = await pv_service.generate_pv(
        meeting_id=meeting_id,
        transcription_id=pv_generate.transcription_id,
        template=pv_generate.template,
        current_user=current_user,
    )
    return pv

@router.get("/{pv_id}", response_model=PVResponse)
async def get_pv(
    request: Request,
    pv_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
):
    pv_service = PVService(db)
    pv = await pv_service.get_pv_by_id(pv_id, current_user)
    return pv

@router.put("/{pv_id}", response_model=PVResponse)
async def update_pv(
    request: Request,
    pv_id: int,
    pv_update: PVUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
):
    pv_service = PVService(db)
    pv = await pv_service.update_pv(pv_id, pv_update, current_user)
    return pv

@router.post("/{pv_id}/validate", response_model=PVValidationResponse, response_model_by_alias=True)
async def validate_pv(
    request: Request,
    pv_id: int,
    pv_validate: PVValidate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
):
    pv_service = PVService(db)
    pv = await pv_service.validate_pv(pv_id, current_user, pv_validate.comment)
    return pv

@router.delete("/{pv_id}", status_code=204)
async def delete_pv(
    request: Request,
    pv_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
):
    pv_service = PVService(db)
    await pv_service.delete_pv(pv_id, current_user)
    return

@router.get("/meeting/{meeting_id}", response_model=List[PVResponse])
async def get_pvs_by_meeting(
    request: Request,
    meeting_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
):
    pv_service = PVService(db)
    pvs = await pv_service.get_pvs_by_meeting(meeting_id, current_user)
    return pvs

@router.post("/{pv_id}/extract-decisions", response_model=PVResponse)
async def extract_decisions_from_pv(
    request: Request,
    pv_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
):
    pv_service = PVService(db)
    pv = await pv_service.get_pv_by_id(pv_id, current_user)
    decisions_str = await extract_decisions(pv.content)
    try:
        decisions_list = json.loads(decisions_str.strip()) if decisions_str else []
    except json.JSONDecodeError:
        decisions_list = []
    
    pv_update_data = PVUpdate(decisions=decisions_list)
    updated_pv = await pv_service.update_pv(pv_id, pv_update_data, current_user)
    return updated_pv

@router.get("/{pv_id}/export/pdf")
async def generate_pv_pdf(
    pv_id: int, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(get_current_user)
):
    pv_service = PVService(db)
    return await pv_service.generate_pv_pdf(pv_id, current_user)

@router.post("/{pv_id}/extract-action-points", response_model=PVResponse)
async def extract_action_points_from_pv(
    request: Request,
    pv_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
):
    pv_service = PVService(db)
    pv = await pv_service.get_pv_by_id(pv_id, current_user)
    action_points_str = await extract_action_points(pv.content)
    try:
        action_points_list = json.loads(action_points_str.strip()) if action_points_str else []
    except json.JSONDecodeError:
        action_points_list = []

    pv_update_data = PVUpdate(action_points=action_points_list)
    updated_pv = await pv_service.update_pv(pv_id, pv_update_data, current_user)
    return updated_pv

@router.get("/{pv_id}/export/docx")
async def generate_pv_docx(
    pv_id: int, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(get_current_user)
):
    pv_service = PVService(db)
    return await pv_service.generate_pv_docx(pv_id, current_user)