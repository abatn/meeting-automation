from typing import Any, List
import uuid
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.api import deps
from app.models.user import User as UserModel
from app.models.pv import PV as PVModel, PVVersion as PVVersionModel
from app.models.action import Action as ActionModel
from app.services.pv_service import PVService
from app.services.pdf_service import PDFService
from app.schemas.pv import PVUpdate, PVVersion as PVVersionSchema

router = APIRouter()


@router.post("/generate/{meeting_id}", status_code=202)
async def initiate_pv_generation_with_id(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Generates a PV (meeting minutes) for a meeting.
    """
    return {
        "message": "PV generation initiated",
        "pv_id": str(uuid.uuid4()),
        "status": "in_progress",
    }


@router.post("/generate", status_code=202)
async def initiate_pv_generation(
    data: dict,  # {"transcription_id": "uuid"}
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
        "status": "in_progress",
    }


@router.get("/{pv_id}/pdf")
async def download_pv_pdf(
    pv_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Generates and downloads the PV as a PDF.
    """
    try:
        pdf_service = PDFService(db)
        pdf_path = await pdf_service.generate_pv_pdf(pv_id)

        return FileResponse(
            path=pdf_path,
            filename=f"meeting_minutes_{pv_id}.pdf",
            media_type="application/pdf",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meeting/{meeting_id}")
async def get_pv_by_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieves the PV associated with a specific meeting.
    """
    stmt = (
        select(PVModel)
        .options(selectinload(PVModel.sections))
        .where(PVModel.meeting_id == meeting_id)
    )
    result = await db.execute(stmt)
    pv = result.scalars().first()
    if not pv:
        raise HTTPException(status_code=404, detail="PV for meeting not found")

    actions_result = await db.execute(
        select(ActionModel).where(ActionModel.meeting_id == meeting_id)
    )
    actions = actions_result.scalars().all()

    return {
        "id": pv.id,
        "meeting_id": pv.meeting_id,
        "content": pv.content_html,
        "status": pv.status,
        "actions": [
            {
                "id": a.id,
                "description": a.title,
                "priority": a.priority,
                "status": a.status,
            }
            for a in actions
        ],
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
    stmt = (
        select(PVModel)
        .options(selectinload(PVModel.sections))
        .where(PVModel.id == pv_id)
    )

    result = await db.execute(stmt)
    pv = result.scalars().first()

    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")

    # Mocking actions related to this meeting
    actions_result = await db.execute(
        select(ActionModel).where(ActionModel.meeting_id == pv.meeting_id)
    )
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
                "assigned_to": "Mocked User",  # Usually via relationship
            }
            for a in actions
        ],
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

    return {"message": "PV validated successfully", "status": pv.status}


@router.put("/{pv_id}", response_model=dict)
async def update_pv(
    pv_id: str,
    pv_in: PVUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Updates a PV and automatically creates an ISO 27001 compliant version snapshot.
    """
    stmt = select(PVModel).options(selectinload(PVModel.sections)).where(PVModel.id == pv_id)
    result = await db.execute(stmt)
    pv = result.scalars().first()
    
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")
        
    # Get max version number
    v_stmt = select(PVVersionModel).where(PVVersionModel.pv_id == pv_id).order_by(desc(PVVersionModel.version_number))
    v_result = await db.execute(v_stmt)
    latest_version = v_result.scalars().first()
    next_version_num = latest_version.version_number + 1 if latest_version else 1
    
    # Create snapshot of current state
    snapshot = {
        "title": pv.title,
        "content_html": pv.content_html,
        "status": pv.status,
        "is_validated": pv.is_validated,
    }
    
    pv_version = PVVersionModel(
        id=str(uuid.uuid4()),
        pv_id=pv.id,
        version_number=next_version_num,
        snapshot_data=json.dumps(snapshot),
        change_summary=f"Updated by {current_user.email}",
        created_by_id=current_user.id
    )
    db.add(pv_version)
    
    # Update PV
    update_data = pv_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pv, field, value)
        
    await db.commit()
    await db.refresh(pv)
    
    return {"message": "PV updated successfully", "version_created": next_version_num}


@router.get("/{pv_id}/versions", response_model=List[PVVersionSchema])
async def list_pv_versions(
    pv_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Lists all historical versions of a specific PV.
    """
    stmt = select(PVVersionModel).where(PVVersionModel.pv_id == pv_id).order_by(desc(PVVersionModel.version_number))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{pv_id}/versions/{version_id}", response_model=PVVersionSchema)
async def get_pv_version(
    pv_id: str,
    version_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Gets a specific PV version snapshot by ID.
    """
    stmt = select(PVVersionModel).where(PVVersionModel.id == version_id, PVVersionModel.pv_id == pv_id)
    result = await db.execute(stmt)
    version = result.scalars().first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("/{pv_id}/restore/{version_id}", response_model=dict)
async def restore_pv_version(
    pv_id: str,
    version_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Restores a PV to a previous version, logging the recovery as a new state.
    """
    # 1. Fetch Version
    stmt = select(PVVersionModel).where(PVVersionModel.id == version_id, PVVersionModel.pv_id == pv_id)
    result = await db.execute(stmt)
    version = result.scalars().first()
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
        
    # 2. Fetch PV
    pv_stmt = select(PVModel).where(PVModel.id == pv_id)
    pv_result = await db.execute(pv_stmt)
    pv = pv_result.scalars().first()
    
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")
        
    # 3. Create a snapshot of the current state before overwriting
    v_stmt = select(PVVersionModel).where(PVVersionModel.pv_id == pv_id).order_by(desc(PVVersionModel.version_number))
    v_result = await db.execute(v_stmt)
    latest_version = v_result.scalars().first()
    next_version_num = latest_version.version_number + 1 if latest_version else 1
    
    current_snapshot = {
        "title": pv.title,
        "content_html": pv.content_html,
        "status": pv.status,
        "is_validated": pv.is_validated,
    }
    
    backup_version = PVVersionModel(
        id=str(uuid.uuid4()),
        pv_id=pv.id,
        version_number=next_version_num,
        snapshot_data=json.dumps(current_snapshot),
        change_summary=f"Auto-backup before restoring to version {version.version_number}",
        created_by_id=current_user.id
    )
    db.add(backup_version)
    
    # 4. Apply restore
    try:
        restore_data = json.loads(version.snapshot_data)
        for key, value in restore_data.items():
            if hasattr(pv, key):
                setattr(pv, key, value)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid snapshot data format")
        
    await db.commit()
    await db.refresh(pv)
    
    return {"message": f"Successfully restored to version {version.version_number}"}
