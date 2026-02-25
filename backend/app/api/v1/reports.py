<<<<<<< HEAD
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.api.deps import get_db, get_current_user
from app.models.user import UserModel
from app.services.report_service import ReportService
from app.schemas.report import (
    ManagerDashboard, MeetingStats, ActionStats, TeamProductivity, EfficiencyTrendPoint
)

router = APIRouter()

def require_manager(current_user: UserModel = Depends(get_current_user)):
    """Dependency um sicherzustellen, dass User Manager/DG ist"""
    if current_user.role not in ["manager", "admin", "dg"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user

@router.get("/manager/dashboard", response_model=ManagerDashboard)
async def get_manager_dashboard(
    current_user: UserModel = Depends(require_manager),
    db: AsyncSession = Depends(get_db)
):
    """Gibt alle Metriken für das Dashboard zurück"""
    service = ReportService(db)
    return await service.get_manager_dashboard(current_user.id)

@router.get("/meetings/stats", response_model=MeetingStats)
async def get_meetings_stats(
    period: str = Query("month", description="Filter period (month, year)"),
    current_user: UserModel = Depends(require_manager),
    db: AsyncSession = Depends(get_db)
):
    service = ReportService(db)
    stats = await service.get_meeting_stats(period)
    return MeetingStats(**stats)

@router.get("/actions/completion", response_model=ActionStats)
async def get_action_completion(
    days: int = Query(30, description="Number of days to look back"),
    current_user: UserModel = Depends(require_manager),
    db: AsyncSession = Depends(get_db)
):
    service = ReportService(db)
    stats = await service.get_action_completion_rate(days)
    return ActionStats(**stats)

@router.get("/team/productivity", response_model=List[TeamProductivity])
async def get_team_productivity(
    current_user: UserModel = Depends(require_manager),
    db: AsyncSession = Depends(get_db)
):
    service = ReportService(db)
    data = await service.get_team_productivity()
    return [TeamProductivity(**item) for item in data]

@router.get("/efficiency/trend", response_model=List[EfficiencyTrendPoint])
async def get_efficiency_trend(
    months: int = Query(6, description="Number of months for trend"),
    current_user: UserModel = Depends(require_manager),
    db: AsyncSession = Depends(get_db)
):
    service = ReportService(db)
    data = await service.get_efficiency_trend(months)
    return [EfficiencyTrendPoint(**item) for item in data]
=======
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from typing import Optional

from app.api import deps
from app.models.user import User as UserModel
from app.models.meeting import Meeting as MeetingModel
from app.models.action import Action as ActionModel

router = APIRouter()

@router.get("/dashboard/{role}")
async def generate_dashboard_data(
    role: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Generates data for role-specific dashboards (DG, Manager, Participant).
    """
    if role not in ["dg", "manager", "participant"]:
        raise HTTPException(status_code=400, detail="Invalid role specified")

    # Mock implementation of dashboard metrics using basic queries
    
    # 1. Total Meetings
    result_meetings = await db.execute(select(func.count(MeetingModel.id)))
    total_meetings = result_meetings.scalar() or 0
    
    # 2. Completed Meetings
    result_completed = await db.execute(
        select(func.count(MeetingModel.id)).where(MeetingModel.status == "completed")
    )
    completed_meetings = result_completed.scalar() or 0
    
    # 3. Pending Actions
    result_pending = await db.execute(
        select(func.count(ActionModel.id)).where(ActionModel.status == "pending")
    )
    pending_actions = result_pending.scalar() or 0
    
    # Mocking complex aggregations for the sake of the prototype
    return {
        "total_meetings": total_meetings,
        "completed_meetings": completed_meetings,
        "pending_actions": pending_actions,
        "meetings_by_month": {"Jan": 10, "Feb": 15},
        "action_status_distribution": {"open": 20, "in_progress": 10, "completed": 70}
    }

@router.get("/export")
async def generate_export_report(
    format: str = Query("pdf", description="Format of the report (pdf or xlsx)"),
    meeting_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Generates a comprehensive report in a specified format (e.g., PDF, Excel).
    """
    if format not in ["pdf", "xlsx"]:
        raise HTTPException(status_code=400, detail="Unsupported format")
        
    # TODO: Implement actual PDF/XLSX generation logic using reportlab/openpyxl
    # For now, return a mock success message representing a download
    return {"message": f"Report generated in {format} format (Mocked)"}
>>>>>>> b4b03e9 (feat: implement missing API routes for actions, reports, transcriptions and pv)
