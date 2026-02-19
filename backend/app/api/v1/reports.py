import logging
from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_db, get_current_active_user
from backend.app.models.user import User, UserRole
from backend.app.schemas.report import (
    DashboardDGResponse, DashboardManagerResponse, DashboardParticipantResponse,
    MeetingReportResponse, ActionReportResponse, ExportRequest
)
from backend.app.services.report_service import report_service
from backend.app.core.security import get_user_permissions
from backend.app.models.action import ActionStatus
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/dashboard/dg", response_model=DashboardDGResponse)
async def get_dg_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve dashboard data for the Directorate General (DG).
    Requires DG or Admin role.
    """
    permissions = get_user_permissions(current_user)
    if UserRole.DG not in permissions and UserRole.ADMIN not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access DG dashboard."
        )
    logger.info(f"User {current_user.id} ({current_user.email}) accessing DG dashboard.")
    return await report_service.get_dg_dashboard_data(db)

@router.get("/dashboard/manager", response_model=DashboardManagerResponse)
async def get_manager_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve dashboard data for a Manager.
    Requires Manager, DG or Admin role.
    """
    permissions = get_user_permissions(current_user)
    if UserRole.MANAGER not in permissions and UserRole.DG not in permissions and UserRole.ADMIN not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access Manager dashboard."
        )
    logger.info(f"User {current_user.id} ({current_user.email}) accessing Manager dashboard.")
    return await report_service.get_manager_dashboard_data(db, current_user.id) # Pass manager_id

@router.get("/dashboard/participant", response_model=DashboardParticipantResponse)
async def get_participant_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve dashboard data for a Participant.
    Accessible by any active user.
    """
    logger.info(f"User {current_user.id} ({current_user.email}) accessing Participant dashboard.")
    return await report_service.get_participant_dashboard_data(db, current_user.id)

@router.get("/meetings", response_model=MeetingReportResponse)
async def get_meetings_report(
    date_range_start: Optional[date] = None,
    date_range_end: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve a report of meetings, with optional date filtering.
    Requires Manager, DG or Admin role.
    """
    permissions = get_user_permissions(current_user)
    if UserRole.MANAGER not in permissions and UserRole.DG not in permissions and UserRole.ADMIN not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access meeting reports."
        )
    logger.info(f"User {current_user.id} ({current_user.email}) accessing meeting report.")
    return await report_service.get_meeting_report(db, date_range_start, date_range_end)

@router.get("/actions", response_model=ActionReportResponse)
async def get_actions_report(
    status: Optional[ActionStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve a report of actions, with optional status filtering.
    Requires Manager, DG or Admin role.
    """
    permissions = get_user_permissions(current_user)
    if UserRole.MANAGER not in permissions and UserRole.DG not in permissions and UserRole.ADMIN not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access action reports."
        )
    logger.info(f"User {current_user.id} ({current_user.email}) accessing action report.")
    return await report_service.get_action_report(db, status)

@router.post("/export", response_class=FileResponse)
async def export_report(
    export_request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export various reports to PDF or Excel.
    Requires Manager, DG or Admin role for most reports.
    """
    permissions = get_user_permissions(current_user)
    if UserRole.MANAGER not in permissions and UserRole.DG not in permissions and UserRole.ADMIN not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to export reports."
        )
    
    logger.info(f"User {current_user.id} ({current_user.email}) requesting report export: {export_request.report_type} as {export_request.format}")

    file_path: str
    media_type: str
    filename: str

    if export_request.report_type == "meetings":
        meeting_report = await report_service.get_meeting_report(db, export_request.date_range_start, export_request.date_range_end)
        if export_request.format == "pdf":
            # Simplified HTML generation for PDF
            html_content = f"<h1>Meeting Report</h1><p>Total Meetings: {meeting_report.total_meetings}</p><p>Filtered Meetings: {meeting_report.filtered_meetings}</p>"
            html_content += "<ul>" + "".join([f"<li>{m['title']} ({m['start_time']})</li>" for m in meeting_report.meetings]) + "</ul>"
            file_path = await report_service.generate_pdf_report(html_content, "meetings_report.pdf")
            media_type = "application/pdf"
            filename = "meetings_report.pdf"
        elif export_request.format == "excel":
            data_for_excel = [m for m in meeting_report.meetings]
            file_path = await report_service.generate_excel_report(data_for_excel, "meetings_report.xlsx")
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = "meetings_report.xlsx"
        else:
            raise HTTPException(status_code=400, detail="Invalid export format for meetings report.")
    
    elif export_request.report_type == "actions":
        action_status_enum = ActionStatus(export_request.action_status) if export_request.action_status else None
        file_path = await report_service.export_action_report(db, action_status_enum)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"action_report_{export_request.action_status or 'all'}.xlsx"

    elif export_request.report_type == "minutes":
        if not export_request.meeting_id:
            raise HTTPException(status_code=400, detail="Meeting ID is required for meeting minutes export.")
        file_path = await report_service.export_meeting_minutes(db, export_request.meeting_id)
        media_type = "application/pdf"
        filename = f"meeting_minutes_{export_request.meeting_id}.pdf"
    
    else:
        raise HTTPException(status_code=400, detail="Invalid report type for export.")

    return FileResponse(path=file_path, media_type=media_type, filename=filename)