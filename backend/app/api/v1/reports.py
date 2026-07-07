from datetime import datetime
from typing import Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.action import Action as ActionModel
from app.models.action import (
    ActionStatus,
)
from app.models.action import Assignment as AssignmentModel
from app.models.meeting import Meeting as MeetingModel
from app.models.meeting import (
    MeetingStatus,
)
from app.models.meeting import Participant as ParticipantModel
from app.models.user import User as UserModel
from app.models.audit_log import AuditLog as AuditLogModel
from app.schemas.audit_log import AuditLog as AuditLogSchema
from app.schemas.report import ActionStats, ManagerDashboard, MeetingStats

from app.services.billing_service import BillingService
from app.services.report_service import ReportService

router = APIRouter()

async def get_client_usage_info(db: AsyncSession, client_id: str) -> dict:
    billing_service = BillingService(db)
    return await billing_service.get_usage_summary(client_id)


@router.get("/dashboard/{role}", response_model=Any)
async def get_dashboard_data(
    role: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Get dashboard data based on user role. Includes strict RBAC validation.
    """
    # --- SECURITY CHECK (Authorization Bypass Fix) ---
    actual_role = current_user.role
    is_privileged = current_user.is_superuser or actual_role in ["dg", "admin", "system_admin"]
    
    if role == "dg" and not is_privileged:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not authorized to access DG dashboard")
        
    if role == "manager" and not (is_privileged or actual_role == "manager"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not authorized to access Manager dashboard")

    usage_info = await get_client_usage_info(db, current_user.client_id)
    report_service = ReportService(db)
    
    if role == "dg" or role == "manager":
        # --- ECHTE DATENBANKLOGIK FÜR DG / MANAGER DASHBOARD ---
        
        # 1. Base Stats via Service
        stats = await report_service.get_manager_dashboard(current_user.id, current_user.client_id, role)
        
        # 2. Total and Completed Meetings (Additional legacy stats if needed)
        total_meetings_query = select(func.count(MeetingModel.id)).where(MeetingModel.client_id == current_user.client_id)
        total_meetings_res = await db.execute(total_meetings_query)
        total_meetings = total_meetings_res.scalar_one()

        # Merge with usage info
        stats["total_meetings"] = total_meetings
        stats["client_usage"] = usage_info
        return stats

    else:  # role == 'participant'
        # --- DATENBANKLOGIK FÜR PARTICIPANT DASHBOARD ---

        # 1. My Upcoming Meetings
        my_upcoming_meetings_list = await report_service.get_upcoming_meetings(current_user.id, current_user.client_id)
        
        # 2. My Open Actions
        my_open_actions_list = await report_service.get_open_actions(current_user.id, current_user.client_id)

        return {
            "my_upcoming_meetings": len(my_upcoming_meetings_list),
            "my_open_actions": len(my_open_actions_list),
            "upcoming_meetings_list": my_upcoming_meetings_list,
            "open_actions_list": my_open_actions_list,
            "client_usage": usage_info
        }


@router.get("/audit-logs", response_model=List[AuditLogSchema])
async def get_audit_logs(
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Get audit logs.
    """
    result = await db.execute(
        select(AuditLogModel)
        .where(AuditLogModel.client_id == current_user.client_id)
        .order_by(AuditLogModel.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


# --- AUTOMATION ENDPOINTS (Internal Use for n8n) ---

@router.get("/automation/meeting/{meeting_id}")
async def get_meeting_details_for_automation(
    meeting_id: str,
    client_id: str = Query(None),
    db: AsyncSession = Depends(deps.get_db),
    api_key_valid: bool = Depends(deps.verify_internal_api_key),
) -> Any:
    """
    Returns meeting details for n8n. Requires client_id for tenant isolation.
    """
    if not client_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="client_id query parameter is required")
    
    stmt = select(MeetingModel).options(selectinload(MeetingModel.participants)).where(
        MeetingModel.id == meeting_id,
        MeetingModel.client_id == client_id,
    )
    result = await db.execute(stmt)
    m = result.scalars().first()
    if not m:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    return {
        "id": m.id,
        "title": m.title,
        "start_time": m.start_time.isoformat(),
        "attendees": [p.email for p in m.participants]
    }


@router.get("/automation/pdf/{meeting_id}")
async def get_meeting_pdf_for_automation(
    meeting_id: str,
    client_id: str = Query(None),
    db: AsyncSession = Depends(deps.get_db),
    api_key_valid: bool = Depends(deps.verify_internal_api_key),
) -> Any:
    """
    Returns the PV PDF for n8n attachment. Requires client_id for tenant isolation.
    """
    if not client_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="client_id query parameter is required")

    from app.models.pv import PV as PVModel
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    from app.services.pdf_service import PDFService
    from app.core.config import settings, get_bucket_name
    import boto3

    pv_stmt = select(PVModel).where(PVModel.meeting_id == meeting_id, PVModel.client_id == client_id)
    pv_res = await db.execute(pv_stmt)
    pv = pv_res.scalars().first()
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found for this meeting")

    # Schritt 1: Prüfe S3 auf OnlyOffice PDF
    pdf_key = f"pv_exports/{pv.id}/final_document.pdf"
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )

    try:
        s3.head_object(Bucket=get_bucket_name(), Key=pdf_key)
        local_pdf_path = f"/tmp/automation_{pv.id}.pdf"
        s3.download_file(get_bucket_name(), pdf_key, local_pdf_path)
        return FileResponse(path=local_pdf_path, filename=f"Protocol_{meeting_id}.pdf")
    except Exception:
        pass

    # Schritt 2: Generiere PDF aus DB-HTML via WeasyPrint
    pdf_service = PDFService(db)
    pdf_path = await pdf_service.generate_pv_pdf(pv_id=pv.id, client_id=pv.client_id)
    return FileResponse(path=pdf_path, filename=f"Protocol_{meeting_id}.pdf")
