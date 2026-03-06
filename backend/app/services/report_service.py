import logging
import json
from datetime import datetime, timedelta
from typing import List, Any
import redis
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
        self.redis_client = redis.Redis(
            host=settings.REDIS_URL.split("//")[1].split(":")[0],
            port=int(settings.REDIS_URL.split(":")[2].split("/")[0]),
            db=1
        )

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

    async def get_meeting_stats(self, period: str = "month") -> dict:
        """Aggregiert Meetings nach Status (cached)"""
        async def compute():
            date_filter = datetime.utcnow() - timedelta(
                days=30 if period == "month" else 365
            )
            query = select(Meeting.status, func.count(Meeting.id)).where(
                Meeting.start_time >= date_filter
            ).group_by(Meeting.status)

            result = await self.db.execute(query)
            counts = {row[0]: row[1] for row in result.all()}
            return {
                "completed": counts.get("completed", 0),
                "scheduled": counts.get("scheduled", 0),
                "cancelled": counts.get("cancelled", 0)
            }
        return await self._get_cached_or_compute(f"reports_meetings_{period}", compute)

    async def get_action_completion_rate(self, days: int = 30) -> dict:
        """Berechnet Aufgaben-Zustände (cached)"""
        async def compute():
            # overdue ist, wenn status = pending und due_date < NOW()
            now = datetime.utcnow()
            query = select(
                func.sum(case((Action.status == 'completed', 1), else_=0)).label(
                    'completed'
                ),
                func.sum(case(
                    (Action.status == 'pending', case((Action.due_date < now, 1),
                     else_=0)), else_=0)
                ).label('overdue'),
                func.sum(case(
                    (Action.status == 'pending', case((Action.due_date >= now, 1),
                     else_=0)), else_=0)
                ).label('pending')
            )
            result = await self.db.execute(query)
            row = result.first()
            return {
                "completed": int(row.completed or 0),
                "overdue": int(row.overdue or 0),
                "pending": int(row.pending or 0)
            }
        return await self._get_cached_or_compute(f"reports_actions_{days}", compute)

    async def get_team_productivity(self) -> List[dict]:
        """Leistung pro Mitarbeiter (cached)"""
        async def compute():
            now = datetime.utcnow()
            query = select(
                UserModel.id,
                UserModel.full_name,
                func.sum(case((Action.status == 'completed', 1), else_=0)).label(
                    'completed'
                ),
                func.sum(case(
                    (Action.status == 'pending', case((Action.due_date < now, 1),
                     else_=0)), else_=0)
                ).label('overdue'),
                func.sum(case(
                    (Action.status == 'pending', case((Action.due_date >= now, 1),
                     else_=0)), else_=0)
                ).label('pending')
            ).join(Action, UserModel.id == Action.assignee_id).group_by(UserModel.id)

            result = await self.db.execute(query)
            data = []
            for row in result.all():
                data.append({
                    "user_id": row.id,
                    "name": row.full_name,
                    "completed": int(row.completed or 0),
                    "overdue": int(row.overdue or 0),
                    "pending": int(row.pending or 0)
                })
            return data
        return await self._get_cached_or_compute("reports_team_prod", compute, ttl=3600)

    async def get_efficiency_trend(self, months: int = 6) -> List[dict]:
        """Trend der Effizienz (cached)"""
        async def compute():
            # Vereinfachte Mock-Implementierung für den Graphen
            trend = []
            now = datetime.utcnow()
            for i in range(months-1, -1, -1):
                month_date = now - timedelta(days=30*i)
                trend.append({
                    "month": month_date.strftime("%b %Y"),
                    "avg_duration_minutes": 45.0 - (i * 2.5),  # Dummy Trend
                    "actions_per_meeting": 3.0 + (i * 0.5)
                })
            return trend
        return await self._get_cached_or_compute(
            f"reports_efficiency_{months}", compute, ttl=86400
        )

    async def get_manager_dashboard(self, manager_id: int) -> dict:
        """Haupt-Dashboard zusammenstellen"""
        meeting_stats = await self.get_meeting_stats()
        action_stats = await self.get_action_completion_rate()
        team_prod = await self.get_team_productivity()
        trend = await self.get_efficiency_trend()

        return {
            "meeting_stats": meeting_stats,
            "action_stats": action_stats,
            "team_productivity": team_prod,
            "efficiency_trend": trend
        }
