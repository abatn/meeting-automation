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
