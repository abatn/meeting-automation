from typing import Optional
import json

from fastapi import APIRouter, Depends, HTTPException, Request  # Import Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession # Import AsyncSession
from typing import List
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from backend.app.api import deps
from backend.app.api.deps import get_current_user
from backend.app.models.user import User
from backend.app.schemas.pv import PVGenerate, PVUpdate, PVValidate, PVResponse, PVValidationResponse # Import PVResponse
from backend.app.services import pv_service
from backend.app.services.audit_service import AuditService, AuditAction
from backend.app.schemas.audit import AuditLogCreate

router = APIRouter()
audit_service = AuditService()

@router.post("/{meeting_id}/generate", response_model=PVResponse)  # Specify response_model
async def generate_pv(
    request: Request,
    meeting_id: int,
    pv_generate: PVGenerate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates a PV for a meeting.
    """
    try:
        pv = await pv_service.generate_pv(
            meeting_id,
            pv_generate.transcription_id,
            pv_generate.template,
            db=db,
            current_user=current_user,
        )
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.GENERATE_PV,
                resource_type="PV",
                resource_id=pv.id,
                details={"meeting_id": meeting_id, "pv_id": pv.id},
                method=request.method,
                path=request.url.path,
                status_code=200,
            ),
        )
        # Eagerly load relationships before passing to Pydantic
        await db.refresh(pv, attribute_names=["validator", "generator", "meeting"])
        return PVResponse.model_validate(pv)
    except HTTPException as e:
        print(f"HTTPException in generate_pv endpoint: {str(e)}")
        import traceback

        traceback.print_exc()
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.GENERATE_PV,
                resource_type="PV",
                resource_id=None,
                details={"meeting_id": meeting_id, "error": str(e.detail)},
                method=request.method,
                path=request.url.path,
                status_code=e.status_code,
            ),
        )
        raise e
    except Exception as e:
        print(f"ERROR IN generate_pv ENDPOINT: {str(e)}")
        import traceback

        traceback.print_exc()
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.GENERATE_PV,
                resource_type="PV",
                resource_id=None,
                details={"meeting_id": meeting_id, "error": str(e)},
                method=request.method,
                path=request.url.path,
                status_code=500,
            ),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{pv_id}", response_model=PVResponse)
async def get_pv(
    request: Request,
    pv_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves a PV by its ID.
    """
    try:
        pv = await pv_service.get_pv_by_id(pv_id, db=db, current_user=current_user)
        return PVResponse.model_validate(pv)
    except Exception as e:
        print(f"ERROR IN get_pv endpoint: {str(e)}")
        import traceback

        traceback.print_exc()
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.GET_PV,
                resource_type="PV",
                resource_id=pv_id,
                details={"pv_id": pv_id, "error": str(e)},
                method=request.method,
                path=request.url.path,
                status_code=500,
            ),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{pv_id}", response_model=PVResponse)  # Specify response_model
async def update_pv(
    pv_id: int, pv_update: PVUpdate, db: Session = Depends(deps.get_db), current_user: User = Depends(get_current_user)
):
    """
    Updates a PV manually.
    """
    try:
        pv = await pv_service.update_pv(pv_id, pv_update, db=db, current_user=current_user)
        return PVResponse.model_validate(pv)
    except HTTPException as e:
        print(f"HTTPException in update_pv endpoint: {str(e)}")
        import traceback

        traceback.print_exc()
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.UPDATE_PV,
                resource_type="PV",
                resource_id=pv_id,
                details={"pv_id": pv_id, "error": str(e)},
                method=request.method,
                path=request.url.path,
                status_code=500,
            ),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pv_id}/validate", response_model=PVValidationResponse)
async def validate_pv(
    request: Request,
    pv_id: int,
    pv_validate: PVValidate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Validates a PV (DG only).
    """
    user_id = current_user.id
    try:
        pv = await pv_service.validate_pv(pv_id, current_user, db=db, comment=pv_validate.comment)
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=user_id,
                action=AuditAction.VALIDATE_PV,
                resource_type="PV",
                resource_id=pv.id,
                details={"pv_id": pv.id, "comment": pv_validate.comment},
                method=request.method,
                path=request.url.path,
                status_code=200,
            ),
        )
        # Eagerly load relationships before passing to Pydantic
        await db.refresh(pv, attribute_names=["validator", "generator", "meeting"])
        return PVValidationResponse.model_validate(pv)
    except HTTPException as e:
        print(f"HTTPException in validate_pv endpoint: {str(e)}")
        import traceback

        traceback.print_exc()
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=user_id,
                action=AuditAction.VALIDATE_PV,
                resource_type="PV",
                resource_id=pv_id,
                details={"pv_id": pv_id, "comment": pv_validate.comment, "error": str(e.detail)},
                method=request.method,
                path=request.url.path,
                status_code=e.status_code,
            ),
        )
        raise e
    except Exception as e:
        print(f"ERROR IN validate_pv ENDPOINT: {str(e)}")
        import traceback

        traceback.print_exc()
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=user_id,
                action=AuditAction.VALIDATE_PV,
                resource_type="PV",
                resource_id=pv_id,
                details={"pv_id": pv_id, "comment": pv_validate.comment, "error": str(e)},
                method=request.method,
                path=request.url.path,
                status_code=500,
            ),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{pv_id}", response_model=PVResponse)  # Specify response_model
async def delete_pv(
    pv_id: int, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(get_current_user)
):
    """
    Deletes a PV (Admin only).
    """
    try:
        pv = await pv_service.delete_pv(pv_id, db=db, current_user=current_user)
        return PVResponse.model_validate(pv)
    except Exception as e:
        print(f"ERROR IN delete_pv ENDPOINT: {str(e)}")
        import traceback

        traceback.print_exc()
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.DELETE_PV,
                resource_type="PV",
                resource_id=pv_id,
                details={"pv_id": pv_id, "error": str(e)},
                method=request.method,
                path=request.url.path,
                status_code=500,
            ),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meeting/{meeting_id}", response_model=PVResponse)  # Specify response_model
async def get_pv_by_meeting(
    meeting_id: int, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(get_current_user)
):
    """
    Retrieves a PV by its meeting ID.
    """
    try:
        pvs = await pv_service.get_pv_by_meeting(meeting_id, db=db, current_user=current_user)
        return [PVResponse.model_validate(pv) for pv in pvs] if pvs else []
    except Exception as e:
        print(f"ERROR IN get_pv_by_meeting ENDPOINT: {str(e)}")
        import traceback

        traceback.print_exc()
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.GET_PV_BY_MEETING,
                resource_type="PV",
                resource_id=meeting_id,
                details={"meeting_id": meeting_id, "error": str(e)},
                method=request.method,
                path=request.url.path,
                status_code=500,
            ),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pv_id}/extract-decisions", response_model=dict)  # Specify response_model
async def extract_decisions_from_pv(
    request: Request,
    pv_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Extracts decisions from a PV.
    """
    try:
        pv = await pv_service.get_pv_by_id(pv_id, db=db, current_user=current_user)
        decisions_str = await pv_service.extract_decisions(pv.content)

        decisions_list = []
        if decisions_str:  # Check if string is not empty
            try:
                decisions_list = json.loads(decisions_str.strip())
            except json.JSONDecodeError as json_e:
                print(f"JSONDecodeError in extract_decisions_from_pv: {json_e}")
                # Log the error and continue with an empty list or raise a specific error
                await audit_service.log_action(
                    db=db,
                    log_data=AuditLogCreate(
                        user_id=current_user.id,
                        action=AuditAction.EXTRACT_DECISIONS,
                        resource_type="PV",
                        resource_id=pv_id,
                        details={
                            "pv_id": pv_id,
                            "error": f"JSON parsing failed: {str(json_e)}",
                            "raw_mistral_response": decisions_str,
                        },
                        method=request.method,
                        path=request.url.path,
                        status_code=500,
                    ),
                )
                decisions_list = []  # Return an empty list in case of parsing error
        pv_update_data = PVUpdate(decisions=decisions_list)
        updated_pv = await pv_service.update_pv(
            pv_id, pv_update_data, db=db, current_user=current_user
        )
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.EXTRACT_DECISIONS,
                resource_type="PV",
                resource_id=pv_id,
                details={"pv_id": pv_id, "decisions": decisions_list},
                method=request.method,
                path=request.url.path,
                status_code=200,
            ),
        )
        return {"pv_id": pv_id, "decisions": decisions_list}
    except HTTPException as e:
        print(f"HTTPException in extract_decisions_from_pv endpoint: {str(e)}")
        import traceback

        traceback.print_exc()
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.EXTRACT_DECISIONS,
                resource_type="PV",
                resource_id=pv_id,
                details={"pv_id": pv_id, "error": str(e.detail)},
                method=request.method,
                path=request.url.path,
                status_code=e.status_code,
            ),
        )
        raise e
    except Exception as e:
        print(f"ERROR IN extract_decisions_from_pv ENDPOINT: {str(e)}")
        import traceback

        traceback.print_exc()
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.EXTRACT_DECISIONS,
                resource_type="PV",
                resource_id=pv_id,
                details={"pv_id": pv_id, "error": str(e)},
                method=request.method,
                path=request.url.path,
                status_code=500,
            ),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{pv_id}/export/pdf")
async def generate_pv_pdf(
    pv_id: int, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(get_current_user)
):
    """
    Generates a PDF from a PV.
    """
    try:
        pv = await pv_service.generate_pv_pdf(pv_id, db=db, current_user=current_user)
        return pv
    except Exception as e:
        print(f"ERROR IN generate_pv_pdf ENDPOINT: {str(e)}")
        import traceback

        traceback.print_exc()
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.GENERATE_PV_PDF,
                resource_type="PV",
                resource_id=pv_id,
                details={"pv_id": pv_id, "error": str(e)},
                method=request.method,
                path=request.url.path,
                status_code=500,
            ),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pv_id}/extract-action-points", response_model=dict)
async def extract_action_points_from_pv(
    request: Request,
    pv_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Extracts action points from a PV.
    """
    try:
        pv = await pv_service.get_pv_by_id(pv_id, db=db, current_user=current_user)
        action_points_str = await pv_service.extract_action_points(pv.content)

        action_points_list = []
        if action_points_str:
            try:
                action_points_list = json.loads(action_points_str.strip())
            except json.JSONDecodeError as json_e:
                await audit_service.log_action(
                    db=db,
                    log_data=AuditLogCreate(
                        user_id=current_user.id,
                        action=AuditAction.EXTRACT_ACTION_POINTS,
                        resource_type="PV",
                        resource_id=pv_id,
                        details={
                            "pv_id": pv_id,
                            "error": f"JSON parsing failed: {str(json_e)}",
                            "raw_mistral_response": action_points_str,
                        },
                        method=request.method,
                        path=request.url.path,
                        status_code=500,
                    ),
                )
                action_points_list = []
        pv_update_data = PVUpdate(action_points=action_points_list)
        updated_pv = await pv_service.update_pv(
            pv_id, pv_update_data, db=db, current_user=current_user
        )
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.EXTRACT_ACTION_POINTS,
                resource_type="PV",
                resource_id=pv_id,
                details={"pv_id": pv_id, "action_points": action_points_list},
                method=request.method,
                path=request.url.path,
                status_code=200,
            ),
        )
        return {"pv_id": pv_id, "action_points": action_points_list}
    except HTTPException as e:
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.EXTRACT_ACTION_POINTS,
                resource_type="PV",
                resource_id=pv_id,
                details={"pv_id": pv_id, "error": str(e.detail)},
                method=request.method,
                path=request.url.path,
                status_code=e.status_code,
            ),
        )
        raise e
    except Exception as e:
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.EXTRACT_ACTION_POINTS,
                resource_type="PV",
                resource_id=pv_id,
                details={"pv_id": pv_id, "error": str(e)},
                method=request.method,
                path=request.url.path,
                status_code=500,
            ),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{pv_id}/export/docx")
async def generate_pv_docx(
    pv_id: int, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(get_current_user)
):
    """
    Generates a Word document from a PV.
    """
    try:
        pv = await pv_service.generate_pv_docx(pv_id, db=db, current_user=current_user)
        return pv
    except Exception as e:
        print(f"ERROR IN generate_pv_docx ENDPOINT: {str(e)}")
        import traceback

        traceback.print_exc()
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=current_user.id,
                action=AuditAction.GENERATE_PV_DOCX,
                resource_type="PV",
                resource_id=pv_id,
                details={"pv_id": pv_id, "error": str(e)},
                method=request.method,
                path=request.url.path,
                status_code=500,
            ),
        )
        raise HTTPException(status_code=500, detail=str(e))
