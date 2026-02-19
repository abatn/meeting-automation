import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, extract, and_

from backend.app.models.user import User, UserRole
from backend.app.models.meeting import Meeting, MeetingStatus
from backend.app.models.action import Action, ActionStatus
from backend.app.models.transcription import Transcription
from backend.app.models.pv import PV
from backend.app.schemas.report import (
    DashboardDGResponse, DashboardManagerResponse, DashboardParticipantResponse,
    MeetingReportResponse, ActionReportResponse, ChartData
)
from backend.app.utils.pdf_generator import generate_pdf_from_html
from backend.app.utils.excel_generator import generate_excel_from_data

logger = logging.getLogger(__name__)

class ReportService:
    async def get_dg_dashboard_data(self, db: AsyncSession) -> DashboardDGResponse:
        logger.info("Generating DG Dashboard data.")
        
        # Total Meetings
        total_meetings = (await db.execute(select(func.count(Meeting.id)))).scalar_one()

        # Meetings per Month
        meetings_per_month_data = (await db.execute(
            select(
                func.strftime('%Y-%m', Meeting.start_time).label('month'),
                func.count(Meeting.id).label('count')
            )
            .group_by('month')
            .order_by('month')
        )).all()
        meetings_per_month_labels = [row.month for row in meetings_per_month_data]
        meetings_per_month_counts = [row.count for row in meetings_per_month_data]
        meetings_per_month_chart = ChartData(
            labels=meetings_per_month_labels,
            datasets=[{"label": "Meetings", "data": meetings_per_month_counts}]
        )

        # Actions
        total_actions = (await db.execute(select(func.count(Action.id)))).scalar_one()
        open_actions = (await db.execute(select(func.count(Action.id)).where(Action.status == ActionStatus.OPEN))).scalar_one()
        completed_actions = (await db.execute(select(func.count(Action.id)).where(Action.status == ActionStatus.COMPLETED))).scalar_one()
        overdue_actions = (await db.execute(select(func.count(Action.id)).where(Action.status == ActionStatus.OVERDUE))).scalar_one()

        # Compliance Rate (simplified: percentage of completed actions)
        compliance_rate = (completed_actions / total_actions * 100) if total_actions > 0 else 0.0

        # Top Performers (simplified: users with most completed actions)
        top_performers_data = (await db.execute(
            select(
                User.full_name,
                func.count(Action.id).label('completed_count')
            )
            .join(Action, User.id == Action.assigned_to)
            .where(Action.status == ActionStatus.COMPLETED)
            .group_by(User.full_name)
            .order_by(func.count(Action.id).desc())
            .limit(5)
        )).all()
        top_performers = [{"name": row.full_name, "completed_actions": row.completed_count} for row in top_performers_data]

        # Action Status Distribution
        action_status_dist_data = (await db.execute(
            select(
                Action.status,
                func.count(Action.id).label('count')
            )
            .group_by(Action.status)
        )).all()
        action_status_dist_labels = [row.status.value for row in action_status_dist_data]
        action_status_dist_counts = [row.count for row in action_status_dist_data]
        action_status_distribution_chart = ChartData(
            labels=action_status_dist_labels,
            datasets=[{"label": "Action Status", "data": action_status_dist_counts}]
        )

        return DashboardDGResponse(
            total_meetings=total_meetings,
            meetings_per_month=meetings_per_month_chart,
            total_actions=total_actions,
            open_actions=open_actions,
            completed_actions=completed_actions,
            overdue_actions=overdue_actions,
            compliance_rate=compliance_rate,
            top_performers=top_performers,
            action_status_distribution=action_status_distribution_chart
        )

    async def get_manager_dashboard_data(self, db: AsyncSession, manager_id: int) -> DashboardManagerResponse:
        logger.info(f"Generating Manager Dashboard data for manager ID: {manager_id}")
        
        # Assuming a manager is associated with a team or can see actions of certain users
        # For simplicity, let's assume a manager can see actions of all participants for now.
        # In a real app, this would involve team/department relationships.

        # Team Overview (e.g., all users who are not admins/DGs)
        team_members = (await db.execute(
            select(User).where(User.role == UserRole.PARTICIPANT)
        )).scalars().all()
        
        team_overview = []
        for member in team_members:
            member_actions = (await db.execute(
                select(Action).where(Action.assigned_to == member.id)
            )).scalars().all()
            open_count = sum(1 for a in member_actions if a.status == ActionStatus.OPEN)
            completed_count = sum(1 for a in member_actions if a.status == ActionStatus.COMPLETED)
            overdue_count = sum(1 for a in member_actions if a.status == ActionStatus.OVERDUE)
            team_overview.append({
                "user_id": member.id,
                "user_name": member.full_name or member.email,
                "open_actions": open_count,
                "completed_actions": completed_count,
                "overdue_actions": overdue_count
            })

        # Outstanding Actions per Team Member
        outstanding_actions_labels = [member["user_name"] for member in team_overview]
        outstanding_actions_data = [member["open_actions"] + member["overdue_actions"] for member in team_overview]
        outstanding_actions_chart = ChartData(
            labels=outstanding_actions_labels,
            datasets=[{"label": "Outstanding Actions", "data": outstanding_actions_data}]
        )

        # Meeting Efficiency (simplified: average duration, average participants)
        meetings = (await db.execute(select(Meeting))).scalars().all()
        total_duration_minutes = 0
        total_participants = 0
        meeting_count = 0
        
        for meeting in meetings:
            if meeting.start_time and meeting.end_time:
                duration = (meeting.end_time - meeting.start_time).total_seconds() / 60
                total_duration_minutes += duration
                meeting_count += 1
            # Assuming meeting.participants is a relationship or can be queried
            # For now, let's just count the organizer
            total_participants += 1 # Simplified

        avg_duration = (total_duration_minutes / meeting_count) if meeting_count > 0 else 0
        avg_participants = (total_participants / meeting_count) if meeting_count > 0 else 0

        meeting_efficiency = {
            "average_meeting_duration_minutes": round(avg_duration, 2),
            "average_participants_per_meeting": round(avg_participants, 2)
        }

        # Upcoming Deadlines (actions due in next 7 days)
        now = datetime.utcnow()
        upcoming_deadlines_data = (await db.execute(
            select(Action)
            .where(
                and_(
                    Action.due_date >= now,
                    Action.due_date <= now + timedelta(days=7),
                    Action.status == ActionStatus.OPEN
                )
            )
            .order_by(Action.due_date)
        )).scalars().all()
        
        upcoming_deadlines = []
        for action in upcoming_deadlines_data:
            assignee_name = action.assignee.full_name if action.assignee else "Unassigned"
            meeting_title = action.meeting.title if action.meeting else "N/A"
            upcoming_deadlines.append({
                "action_id": action.id,
                "description": action.description,
                "due_date": action.due_date.isoformat(),
                "assigned_to": assignee_name,
                "meeting_title": meeting_title
            })

        return DashboardManagerResponse(
            team_overview=team_overview,
            outstanding_actions_per_team_member=outstanding_actions_chart,
            meeting_efficiency=meeting_efficiency,
            upcoming_deadlines=upcoming_deadlines
        )

    async def get_participant_dashboard_data(self, db: AsyncSession, user_id: int) -> DashboardParticipantResponse:
        logger.info(f"Generating Participant Dashboard data for user ID: {user_id}")

        # My Open Actions
        my_open_actions_data = (await db.execute(
            select(Action)
            .where(
                and_(
                    Action.assigned_to == user_id,
                    Action.status == ActionStatus.OPEN
                )
            )
            .order_by(Action.due_date)
        )).scalars().all()
        my_open_actions = []
        for action in my_open_actions_data:
            meeting_title = action.meeting.title if action.meeting else "N/A"
            my_open_actions.append({
                "action_id": action.id,
                "description": action.description,
                "due_date": action.due_date.isoformat() if action.due_date else None,
                "meeting_title": meeting_title
            })

        # My Upcoming Meetings (meetings where user is organizer or participant)
        now = datetime.utcnow()
        my_upcoming_meetings_data = (await db.execute(
            select(Meeting)
            .where(
                and_(
                    Meeting.start_time >= now,
                    Meeting.organizer_id == user_id # Simplified, needs proper participant relationship
                )
            )
            .order_by(Meeting.start_time)
            .limit(5)
        )).scalars().all()
        my_upcoming_meetings = []
        for meeting in my_upcoming_meetings_data:
            my_upcoming_meetings.append({
                "meeting_id": meeting.id,
                "title": meeting.title,
                "start_time": meeting.start_time.isoformat(),
                "location": meeting.location
            })

        # My Transcriptions (transcriptions from meetings where user was present/organizer)
        my_transcriptions_data = (await db.execute(
            select(Transcription)
            .join(Meeting, Transcription.meeting_id == Meeting.id)
            .where(Meeting.organizer_id == user_id) # Simplified
            .order_by(Transcription.created_at.desc())
            .limit(5)
        )).scalars().all()
        my_transcriptions = []
        for transcription in my_transcriptions_data:
            meeting_title = transcription.meeting.title if transcription.meeting else "N/A"
            my_transcriptions.append({
                "transcription_id": transcription.id,
                "meeting_title": meeting_title,
                "created_at": transcription.created_at.isoformat()
            })

        # Recent Activity (e.g., last 5 audit logs related to the user)
        recent_activity_data = (await db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(5)
        )).scalars().all()
        recent_activity = []
        for activity in recent_activity_data:
            recent_activity.append({
                "event_type": activity.event_type,
                "details": activity.details,
                "timestamp": activity.timestamp.isoformat()
            })

        return DashboardParticipantResponse(
            my_open_actions=my_open_actions,
            my_upcoming_meetings=my_upcoming_meetings,
            my_transcriptions=my_transcriptions,
            recent_activity=recent_activity
        )

    async def get_meeting_report(self, db: AsyncSession, date_range_start: Optional[date], date_range_end: Optional[date]) -> MeetingReportResponse:
        logger.info(f"Generating Meeting Report for date range: {date_range_start} to {date_range_end}")
        query = select(Meeting)
        if date_range_start:
            query = query.where(Meeting.start_time >= datetime.combine(date_range_start, datetime.min.time()))
        if date_range_end:
            query = query.where(Meeting.start_time <= datetime.combine(date_range_end, datetime.max.time()))
        
        meetings = (await db.execute(query.order_by(Meeting.start_time.desc()))).scalars().all()
        
        meeting_data = []
        for meeting in meetings:
            organizer_name = meeting.organizer.full_name if meeting.organizer else "N/A"
            meeting_data.append({
                "id": meeting.id,
                "title": meeting.title,
                "description": meeting.description,
                "start_time": meeting.start_time.isoformat(),
                "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
                "organizer": organizer_name,
                "status": meeting.status.value
            })
        
        total_meetings_count = (await db.execute(select(func.count(Meeting.id)))).scalar_one()

        return MeetingReportResponse(
            meetings=meeting_data,
            total_meetings=total_meetings_count,
            filtered_meetings=len(meetings)
        )

    async def get_action_report(self, db: AsyncSession, action_status: Optional[ActionStatus]) -> ActionReportResponse:
        logger.info(f"Generating Action Report for status: {action_status}")
        query = select(Action)
        if action_status:
            query = query.where(Action.status == action_status)
        
        actions = (await db.execute(query.order_by(Action.due_date))).scalars().all()

        action_data = []
        for action in actions:
            assignee_name = action.assignee.full_name if action.assignee else "Unassigned"
            meeting_title = action.meeting.title if action.meeting else "N/A"
            action_data.append({
                "id": action.id,
                "description": action.description,
                "due_date": action.due_date.isoformat() if action.due_date else None,
                "assigned_to": assignee_name,
                "meeting_title": meeting_title,
                "status": action.status.value,
                "priority": action.priority
            })
        
        total_actions_count = (await db.execute(select(func.count(Action.id)))).scalar_one()

        return ActionReportResponse(
            actions=action_data,
            total_actions=total_actions_count,
            filtered_actions=len(actions)
        )

    async def generate_pdf_report(self, html_content: str, filename: str) -> str:
        logger.info(f"Generating PDF report: {filename}")
        # This will save the PDF to a temporary location or return bytes
        # For simplicity, let's assume it returns a path to the generated PDF
        pdf_path = await generate_pdf_from_html(html_content, filename)
        return pdf_path

    async def generate_excel_report(self, data: List[Dict[str, Any]], filename: str) -> str:
        logger.info(f"Generating Excel report: {filename}")
        # This will save the Excel to a temporary location or return bytes
        # For simplicity, let's assume it returns a path to the generated Excel
        excel_path = await generate_excel_from_data(data, filename)
        return excel_path

    async def export_meeting_minutes(self, db: AsyncSession, meeting_id: int) -> str:
        logger.info(f"Exporting meeting minutes for meeting ID: {meeting_id}")
        meeting = await db.get(Meeting, meeting_id)
        if not meeting:
            raise ValueError(f"Meeting with ID {meeting_id} not found.")
        
        # Fetch associated transcription, PV, actions
        transcription = (await db.execute(select(Transcription).where(Transcription.meeting_id == meeting_id))).scalars().first()
        pv = (await db.execute(select(PV).where(PV.meeting_id == meeting_id))).scalars().first()
        actions = (await db.execute(select(Action).where(Action.meeting_id == meeting_id))).scalars().all()

        # Generate HTML content for meeting minutes
        html_content = f"""
        <h1>Meeting Minutes: {meeting.title}</h1>
        <p><strong>Date:</strong> {meeting.start_time.strftime('%Y-%m-%d %H:%M')}</p>
        <p><strong>Organizer:</strong> {meeting.organizer.full_name if meeting.organizer else 'N/A'}</p>
        <p><strong>Description:</strong> {meeting.description}</p>

        <h2>Transcription</h2>
        <p>{transcription.content if transcription else 'No transcription available.'}</p>

        <h2>Protocol Template (PV)</h2>
        <p>{pv.content if pv else 'No PV available.'}</p>

        <h2>Actions</h2>
        <ul>
            {''.join([f'<li>{a.description} (Assigned to: {a.assignee.full_name if a.assignee else "N/A"}, Due: {a.due_date.strftime("%Y-%m-%d") if a.due_date else "N/A"}, Status: {a.status.value})</li>' for a in actions]) if actions else '<li>No actions recorded.</li>'}
        </ul>
        """
        filename = f"meeting_minutes_{meeting_id}.pdf"
        pdf_path = await self.generate_pdf_report(html_content, filename)
        return pdf_path

    async def export_action_report(self, db: AsyncSession, action_status: Optional[ActionStatus]) -> str:
        logger.info(f"Exporting action report for status: {action_status}")
        action_report_data = await self.get_action_report(db, action_status)
        
        # Convert Pydantic model to list of dicts for Excel export
        data_for_excel = [action.dict() for action in action_report_data.actions]
        
        filename = f"action_report_{action_status.value if action_status else 'all'}.xlsx"
        excel_path = await self.generate_excel_report(data_for_excel, filename)
        return excel_path

report_service = ReportService()