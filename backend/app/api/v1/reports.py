from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas.report import ManagerDashboard, MeetingStats, ActionStats
from app.models.user import User as UserModel
from app.models.meeting import (
    Meeting as MeetingModel,
    MeetingStatus,
    Participant as ParticipantModel,
)
from app.models.action import (
    Action as ActionModel,
    ActionStatus,
    Assignment as AssignmentModel,
)


router = APIRouter()


@router.get("/dashboard/{role}", response_model=Any)
async def get_dashboard_data(
    role: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Get dashboard data based on user role.
    """
    if role == 'dg':
        # --- ECHTE DATENBANKLOGIK FÜR DG DASHBOARD ---

        # 1. Total and Completed Meetings
        total_meetings_query = select(func.count(MeetingModel.id))
        completed_meetings_query = select(func.count(MeetingModel.id)).where(
            MeetingModel.status == MeetingStatus.COMPLETED
        )

        total_meetings_res = await db.execute(total_meetings_query)
        completed_meetings_res = await db.execute(completed_meetings_query)

        total_meetings = total_meetings_res.scalar_one()
        completed_meetings = completed_meetings_res.scalar_one()

        # 2. Pending Actions
        pending_actions_query = select(func.count(ActionModel.id)).where(
            ActionModel.status == ActionStatus.PENDING
        )
        pending_actions_res = await db.execute(pending_actions_query)
        pending_actions = pending_actions_res.scalar_one()

        # 3. Action Status Distribution
        action_dist_query = select(
            ActionModel.status, func.count(ActionModel.id)
        ).group_by(ActionModel.status)
        action_dist_res = await db.execute(action_dist_query)
        action_status_distribution = {
            status.name.lower(): count for status, count in action_dist_res.all()
        }

        return {
            "total_meetings": total_meetings,
            "completed_meetings": completed_meetings,
            "pending_actions": pending_actions,
            "action_status_distribution": {
                "completed": action_status_distribution.get('completed', 0),
                "in_progress": action_status_distribution.get('in_progress', 0),
                "open": action_status_distribution.get('pending', 0)
            }
        }

    elif role == 'manager':
        # --- DATENBANKLOGIK FÜR MANAGER DASHBOARD ---

        # 1. Managed User IDs
        managed_user_ids = [report.id for report in current_user.reports]
        if not managed_user_ids:
            return ManagerDashboard(
                meeting_stats=MeetingStats(total=0, completed=0, scheduled=0),
                action_stats=ActionStats(pending=0, completed=0),
                team_members_count=0,
                team_productivity=[],
                efficiency_trend=[]
            )

        # 2. Total and Completed Meetings for Team
        team_meetings_query = select(func.count(MeetingModel.id)) \
            .join(ParticipantModel, MeetingModel.id == ParticipantModel.meeting_id) \
            .where(ParticipantModel.user_id.in_(managed_user_ids))

        team_completed_meetings_query = select(func.count(MeetingModel.id)) \
            .join(ParticipantModel, MeetingModel.id == ParticipantModel.meeting_id) \
            .where(ParticipantModel.user_id.in_(managed_user_ids)) \
            .where(MeetingModel.status == MeetingStatus.COMPLETED)

        total_team_meetings = (await db.execute(team_meetings_query)).scalar_one()
        completed_team_meetings = (
            await db.execute(team_completed_meetings_query)
        ).scalar_one()

        # 3. Pending Actions for Team
        team_pending_actions_query = select(func.count(ActionModel.id)) \
            .join(AssignmentModel, ActionModel.id == AssignmentModel.action_id) \
            .where(AssignmentModel.user_id.in_(managed_user_ids)) \
            .where(ActionModel.status == ActionStatus.PENDING)

        pending_team_actions = (await db.execute(team_pending_actions_query)).scalar_one()

        # 4. Completed Actions for Team
        team_completed_actions_query = select(func.count(ActionModel.id)) \
            .join(AssignmentModel, ActionModel.id == AssignmentModel.action_id) \
            .where(AssignmentModel.user_id.in_(managed_user_ids)) \
            .where(ActionModel.status == ActionStatus.COMPLETED)

        completed_team_actions = (
            await db.execute(team_completed_actions_query)
        ).scalar_one()

        return ManagerDashboard(
            meeting_stats=MeetingStats(
                total=total_team_meetings,
                completed=completed_team_meetings,
                scheduled=total_team_meetings - completed_team_meetings
            ),
            action_stats=ActionStats(
                pending=pending_team_actions,
                completed=completed_team_actions
            ),
            team_members_count=len(managed_user_ids),
            team_productivity=[],
            efficiency_trend=[]
        )

    else:  # role == 'participant'
        # --- DATENBANKLOGIK FÜR PARTICIPANT DASHBOARD ---

        # 1. My Upcoming Meetings
        my_upcoming_meetings_query = select(func.count(MeetingModel.id)) \
            .join(ParticipantModel, MeetingModel.id == ParticipantModel.meeting_id) \
            .where(ParticipantModel.user_id == current_user.id) \
            .where(MeetingModel.end_time > datetime.utcnow())

        my_upcoming_meetings = (
            await db.execute(my_upcoming_meetings_query)
        ).scalar_one()

        # 2. My Open Actions
        my_open_actions_query = select(func.count(ActionModel.id)) \
            .join(AssignmentModel, ActionModel.id == AssignmentModel.action_id) \
            .where(AssignmentModel.user_id == current_user.id) \
            .where(ActionModel.status == ActionStatus.PENDING)

        my_open_actions = (await db.execute(my_open_actions_query)).scalar_one()

        return {
            "my_upcoming_meetings": my_upcoming_meetings,
            "my_open_actions": my_open_actions
        }
