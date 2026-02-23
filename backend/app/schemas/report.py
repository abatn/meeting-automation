from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class StatusCount(BaseModel):
    status: str
    count: int

class MeetingStats(BaseModel):
    completed: int = 0
    scheduled: int = 0
    cancelled: int = 0

class ActionStats(BaseModel):
    pending: int = 0
    completed: int = 0
    overdue: int = 0

class TeamProductivity(BaseModel):
    user_id: int
    name: str
    completed: int
    overdue: int
    pending: int

class EfficiencyTrendPoint(BaseModel):
    month: str
    avg_duration_minutes: float
    actions_per_meeting: float

class ManagerDashboard(BaseModel):
    meeting_stats: MeetingStats
    action_stats: ActionStats
    team_productivity: List[TeamProductivity]
    efficiency_trend: List[EfficiencyTrendPoint]
