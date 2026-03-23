import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Any
import redis.asyncio as redis
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.meeting import Meeting
from app.models.action import Action
from app.models.user import User as UserModel

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # Initialize redis asynchronously, from_url is safer
        self.redis_client = redis.from_url(settings.REDIS_URL, db=1)

    async def _get_cached_or_compute(
        self, key: str, compute_func, ttl: int = 1800
    ) -> Any:
        """Helper: Versucht Daten aus Redis zu laden, berechnet sonst neu"""
        try:
            cached_data = await self.redis_client.get(key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Redis cache error: {e}")

        data = await compute_func()

        try:
            await self.redis_client.setex(key, ttl, json.dumps(data))
        except Exception as e:
            logger.warning(f"Redis cache save error: {e}")

        return data

    async def get_meeting_stats(self, client_id: str, period: str = "month") -> dict:
        """Aggregiert Meetings nach Status (cached)"""

        async def compute():
            date_filter = datetime.utcnow() - timedelta(
                days=30 if period == "month" else 365
            )
            query = (
                select(Meeting.status, func.count(Meeting.id))
                .where(Meeting.client_id == client_id)
                .where(Meeting.start_time >= date_filter)
                .group_by(Meeting.status)
            )

            result = await self.db.execute(query)
            counts = {row[0]: row[1] for row in result.all()}
            return {
                "completed": counts.get("completed", 0),
                "scheduled": counts.get("scheduled", 0),
                "cancelled": counts.get("cancelled", 0),
            }

        return await self._get_cached_or_compute(f"reports_meetings_{client_id}_{period}", compute)

    async def get_action_completion_rate(self, client_id: str, days: int = 30) -> dict:
        """Berechnet Aufgaben-Zustände (cached)"""

        async def compute():
            # overdue ist, wenn status = pending und due_date < NOW()
            now = datetime.utcnow()
            query = select(
                func.sum(case((Action.status == "COMPLETED", 1), else_=0)).label(
                    "completed"
                ),
                func.sum(
                    case(
                        (
                            Action.status == "PENDING",
                            case((Action.due_date < now, 1), else_=0),
                        ),
                        else_=0,
                    )
                ).label("overdue"),
                func.sum(
                    case(
                        (
                            Action.status == "PENDING",
                            case((Action.due_date >= now, 1), (Action.due_date.is_(None), 1), else_=0),
                        ),
                        else_=0,
                    )
                ).label("pending"),
            ).where(Action.client_id == client_id)
            result = await self.db.execute(query)
            row = result.first()
            return {
                "completed": int(row.completed or 0),
                "overdue": int(row.overdue or 0),
                "pending": int(row.pending or 0),
            }

        return await self._get_cached_or_compute(f"reports_actions_{client_id}_{days}", compute)

    async def get_team_productivity(self, client_id: str) -> List[dict]:
        """Leistung pro Mitarbeiter (cached)"""

        async def compute():
            now = datetime.utcnow()
            from app.models.action import Assignment
            # Use distinct names from both assignments and users
            query = (
                select(
                    func.coalesce(UserModel.full_name, Assignment.external_name).label("name"),
                    func.sum(case((Action.status == "completed", 1), else_=0)).label(
                        "completed"
                    ),
                    func.sum(
                        case(
                            (
                                Action.status == "pending",
                                case((Action.due_date < now, 1), else_=0),
                            ),
                            else_=0,
                        )
                    ).label("overdue"),
                    func.sum(
                        case(
                            (
                                Action.status == "pending",
                                case((Action.due_date >= now, 1), (Action.due_date.is_(None), 1), else_=0),
                            ),
                            else_=0,
                        )
                    ).label("pending"),
                )
                .select_from(Assignment)
                .join(Action, Action.id == Assignment.action_id)
                .outerjoin(UserModel, UserModel.id == Assignment.user_id)
                .where(Action.client_id == client_id)
                .group_by(func.coalesce(UserModel.full_name, Assignment.external_name))
            )

            result = await self.db.execute(query)
            data = []
            for row in result.all():
                if not row.name: continue
                data.append(
                    {
                        "user_id": str(uuid.uuid4()),
                        "name": row.name,
                        "completed": int(row.completed or 0),
                        "overdue": int(row.overdue or 0),
                        "pending": int(row.pending or 0),
                    }
                )
            return data

        return await self._get_cached_or_compute(f"reports_team_prod_{client_id}", compute, ttl=3600)

    async def get_efficiency_trend(self, client_id: str, months: int = 6) -> List[dict]:
        """Trend der Effizienz (cached)"""

        async def compute():
            # Vereinfachte Mock-Implementierung für den Graphen
            trend = []
            now = datetime.utcnow()
            for i in range(months - 1, -1, -1):
                month_date = now - timedelta(days=30 * i)
                trend.append(
                    {
                        "month": month_date.strftime("%b %Y"),
                        "avg_duration_minutes": 45.0 - (i * 2.5),  # Dummy Trend
                        "actions_per_meeting": 3.0 + (i * 0.5),
                    }
                )
            return trend

        return await self._get_cached_or_compute(
            f"reports_efficiency_{client_id}_{months}", compute, ttl=86400
        )

    async def get_manager_dashboard(self, manager_id: str, client_id: str) -> dict:
        """Haupt-Dashboard zusammenstellen"""
        meeting_stats = await self.get_meeting_stats(client_id)
        action_stats = await self.get_action_completion_rate(client_id)
        team_prod = await self.get_team_productivity(client_id)
        trend = await self.get_efficiency_trend(client_id)

        return {
            "meeting_stats": meeting_stats,
            "action_stats": action_stats,
            "team_productivity": team_prod,
            "efficiency_trend": trend,
        }

    async def get_upcoming_meetings(self, user_id: str, client_id: str, limit: int = 5) -> List[dict]:
        from app.models.meeting import Participant
        from sqlalchemy import or_
        now = datetime.utcnow()
        # Meetings where user is participant OR creator
        query = (
            select(Meeting)
            .outerjoin(Participant)
            .where(
                Meeting.client_id == client_id,
                Meeting.start_time >= now,
                or_(Participant.user_id == user_id, Meeting.creator_id == user_id)
            )
            .order_by(Meeting.start_time.asc())
            .distinct()
            .limit(limit)
        )
        result = await self.db.execute(query)
        meetings = result.scalars().all()
        return [
            {
                "id": m.id,
                "title": m.title,
                "start_time": m.start_time.isoformat(),
                "status": m.status
            } for m in meetings
        ]

    async def get_open_actions(self, user_id: str, client_id: str, limit: int = 5) -> List[dict]:
        from app.models.action import Assignment
        from sqlalchemy import or_
        # For the personal dashboard, show actions assigned to me 
        # OR unassigned actions in meetings I created/participated in? 
        # Let's keep it simple: Actions assigned to me. 
        # To see the newly created AI actions, they MUST be assigned.
        query = (
            select(Action)
            .join(Assignment)
            .where(
                Action.client_id == client_id,
                Action.status == "pending",
                Assignment.user_id == user_id
            )
            .order_by(Action.due_date.asc().nulls_last())
            .limit(limit)
        )
        result = await self.db.execute(query)
        actions = result.scalars().all()
        return [
            {
                "id": a.id,
                "title": a.title,
                "due_date": a.due_date.isoformat() if a.due_date else None,
                "priority": a.priority
            } for a in actions
        ]
