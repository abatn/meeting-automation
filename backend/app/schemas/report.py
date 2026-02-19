from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import date

class ChartData(BaseModel):
    labels: List[str]
    datasets: List[Dict[str, Any]]

class DashboardDGResponse(BaseModel):
    total_meetings: int
    meetings_per_month: ChartData
    total_actions: int
    open_actions: int
    completed_actions: int
    overdue_actions: int
    compliance_rate: float
    top_performers: List[Dict[str, Any]]
    action_status_distribution: ChartData

class DashboardManagerResponse(BaseModel):
    team_overview: List[Dict[str, Any]]
    outstanding_actions_per_team_member: ChartData
    meeting_efficiency: Dict[str, Any]
    upcoming_deadlines: List[Dict[str, Any]]

class DashboardParticipantResponse(BaseModel):
    my_open_actions: List[Dict[str, Any]]
    my_upcoming_meetings: List[Dict[str, Any]]
    my_transcriptions: List[Dict[str, Any]]
    recent_activity: List[Dict[str, Any]]

class MeetingReportResponse(BaseModel):
    meetings: List[Dict[str, Any]]
    total_meetings: int
    filtered_meetings: int

class ActionReportResponse(BaseModel):
    actions: List[Dict[str, Any]]
    total_actions: int
    filtered_actions: int

class ExportRequest(BaseModel):
    format: str # e.g., "pdf", "excel"
    date_range_start: Optional[date]
    date_range_end: Optional[date]
    report_type: str # e.g., "meetings", "actions", "minutes"
    meeting_id: Optional[int] = None # For meeting minutes export
    action_status: Optional[str] = None # For action report