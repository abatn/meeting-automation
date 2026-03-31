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
            counts = {}
            for row in result.all():
                status_key = row[0].value if hasattr(row[0], 'value') else str(row[0]).lower()
                # If enum is returned as string "MeetingStatus.PLANNED", extract the part after dot, or if it's already "planned"
                if "." in status_key:
                    status_key = status_key.split(".")[-1].lower()
                counts[status_key] = row[1]
                
            return {
                "total": sum(counts.values()),
                "completed": counts.get("completed", 0),
                "scheduled": counts.get("planned", 0) + counts.get("in_progress", 0),
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

    async def get_team_productivity(self, client_id: str, manager_id: str = None, role: str = "dg") -> List[dict]:
        """Leistung pro Mitarbeiter (cached). Manager sieht nur sein Team, DG sieht alle."""

        async def compute():
            now = datetime.utcnow()
            from app.models.action import Assignment
            # Use distinct names from both assignments and users
            query = (
                select(
                    func.coalesce(UserModel.full_name, Assignment.external_name).label("name"),
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
                )
                .select_from(Assignment)
                .join(Action, Action.id == Assignment.action_id)
                .outerjoin(UserModel, UserModel.id == Assignment.user_id)
                .where(Action.client_id == client_id)
            )

            if role == "manager" and manager_id:
                # Manager darf nur die Aufgaben seines Teams (inkl. sich selbst) sehen
                team_query = select(UserModel.id).where(
                    UserModel.manager_id == manager_id,
                    UserModel.client_id == client_id # Defense in depth
                )
                team_res = await self.db.execute(team_query)
                team_ids = [row[0] for row in team_res.all()]
                team_ids.append(manager_id)
                query = query.where(Assignment.user_id.in_(team_ids))

            query = query.group_by(func.coalesce(UserModel.full_name, Assignment.external_name))

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

        # Der Cache-Key muss nun den Manager und die Rolle beinhalten, um Datenlecks zwischen Abteilungen zu verhindern!
        cache_key = f"reports_team_prod_{client_id}_{role}_{manager_id}" if role == "manager" else f"reports_team_prod_{client_id}_dg"
        return await self._get_cached_or_compute(cache_key, compute, ttl=3600)

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

    async def get_kpi_trends(self, client_id: str) -> dict:
        """Calculates trends (current vs. previous month) for Meetings and Actions."""
        async def compute():
            now = datetime.utcnow()
            first_day_current = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            first_day_prev = (first_day_current - timedelta(days=1)).replace(day=1)
            last_day_prev = first_day_current - timedelta(seconds=1)

            # 1. Meetings Current vs Previous
            query_curr_meetings = select(func.count(Meeting.id)).where(
                Meeting.client_id == client_id,
                Meeting.start_time >= first_day_current
            )
            query_prev_meetings = select(func.count(Meeting.id)).where(
                Meeting.client_id == client_id,
                Meeting.start_time >= first_day_prev,
                Meeting.start_time <= last_day_prev
            )
            
            res_curr = await self.db.execute(query_curr_meetings)
            res_prev = await self.db.execute(query_prev_meetings)
            curr_meetings = res_curr.scalar() or 0
            prev_meetings = res_prev.scalar() or 0

            # 2. Completed Actions Current vs Previous
            query_curr_actions = select(func.count(Action.id)).where(
                Action.client_id == client_id,
                Action.status == "COMPLETED",
                Action.updated_at >= first_day_current
            )
            query_prev_actions = select(func.count(Action.id)).where(
                Action.client_id == client_id,
                Action.status == "COMPLETED",
                Action.updated_at >= first_day_prev,
                Action.updated_at <= last_day_prev
            )

            res_curr_a = await self.db.execute(query_curr_actions)
            res_prev_a = await self.db.execute(query_prev_actions)
            curr_actions = res_curr_a.scalar() or 0
            prev_actions = res_prev_a.scalar() or 0

            def calc_trend(curr, prev):
                if prev == 0:
                    return {"percent": 100 if curr > 0 else 0, "direction": "up" if curr > 0 else "neutral"}
                diff = ((curr - prev) / prev) * 100
                return {
                    "percent": round(abs(diff), 1),
                    "direction": "up" if diff > 0 else ("down" if diff < 0 else "neutral")
                }

            return {
                "meetings": calc_trend(curr_meetings, prev_meetings),
                "completion_rate": calc_trend(curr_actions, prev_actions)
            }

        return await self._get_cached_or_compute(f"reports_trends_{client_id}", compute, ttl=3600)

    async def get_manager_dashboard(self, manager_id: str, client_id: str, role: str = "manager") -> dict:
        """Haupt-Dashboard zusammenstellen. Trennt zwischen 'dg' (ganze Firma) und 'manager' (nur Team)."""
        meeting_stats = await self.get_meeting_stats(client_id)
        action_stats = await self.get_action_completion_rate(client_id)
        
        # Gebe die Rolle an get_team_productivity weiter!
        team_prod = await self.get_team_productivity(client_id, manager_id, role)
        
        trend = await self.get_efficiency_trend(client_id)
        
        # NEU: KPI Trends
        kpi_trends = await self.get_kpi_trends(client_id)
        
        # NEU: Team-Listen für Meetings und Actions (Rollenbasiert gefiltert!)
        upcoming_meetings = await self.get_team_upcoming_meetings(manager_id, client_id, role=role)
        open_actions = await self.get_team_open_actions(manager_id, client_id, role=role)

        # NEU: Audit Logs (letzte 5)
        from app.models.audit_log import AuditLog
        audit_query = select(AuditLog).where(AuditLog.client_id == client_id).order_by(AuditLog.timestamp.desc()).limit(5)
        audit_res = await self.db.execute(audit_query)
        recent_audit_logs = [
            {
                "id": str(log.id),
                "action": log.action,
                "table_name": log.table_name,
                "timestamp": log.timestamp.isoformat(),
                "user_id": log.user_id
            } for log in audit_res.scalars().all()
        ]

        # NEU: System Health
        from app.services.monitoring_service import MonitoringService
        health_summary = {
            "api": "healthy",
            "ai": "healthy",
            "storage": "healthy"
        }
        try:
            db_metrics = await MonitoringService.get_database_metrics(self.db)
            ai_metrics = await MonitoringService.get_ai_metrics()
            minio_metrics = await MonitoringService.get_minio_metrics()
            
            health_summary = {
                "api": db_metrics.get("status", "healthy"),
                "ai": ai_metrics.get("mistral", {}).get("status", "healthy"),
                "storage": minio_metrics.get("status", "healthy")
            }
        except Exception as e:
            logger.error(f"Failed to fetch health for dashboard: {e}")

        return {
            "meeting_stats": meeting_stats,
            "action_stats": action_stats,
            "team_productivity": team_prod,
            "efficiency_trend": trend,
            "upcoming_meetings_list": upcoming_meetings,
            "open_actions_list": open_actions,
            "team_members_count": len(team_prod),
            "kpi_trends": kpi_trends,
            "recent_audit_logs": recent_audit_logs,
            "system_health": health_summary
        }

    async def get_team_upcoming_meetings(self, manager_id: str, client_id: str, limit: int = 10, role: str = "manager") -> List[dict]:
        """Holt Meetings der Firma (DG) oder des eigenen Teams (Manager)."""
        from app.models.meeting import Participant
        from sqlalchemy import or_
        
        now = datetime.utcnow()
        
        query = (
            select(Meeting)
            .outerjoin(Participant)
            .where(
                Meeting.client_id == client_id,
                Meeting.status != "cancelled", # Filter cancelled as per protocol
                Meeting.start_time >= (now - timedelta(hours=2)) # Show in-progress too
            )
        )

        if role == "manager":
            # 1. Teammitglieder finden (direkte Reports)
            team_query = select(UserModel.id).where(
                UserModel.manager_id == manager_id,
                UserModel.client_id == client_id # Defense in depth
            )
            team_res = await self.db.execute(team_query)
            team_ids = [row[0] for row in team_res.all()]
            team_ids.append(manager_id) # Manager selbst einbeziehen
            
            # Meetings where any team member is participant OR creator
            query = query.where(
                or_(Participant.user_id.in_(team_ids), Meeting.creator_id.in_(team_ids))
            )

        query = (
            query
            .order_by(
                case(
                    (Meeting.status == "in_progress", 0),
                    (Meeting.status == "planned", 1),
                    else_=2
                ),
                Meeting.start_time.asc()
            )
            .group_by(Meeting.id)
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

    async def get_team_open_actions(self, manager_id: str, client_id: str, limit: int = 10, role: str = "manager") -> List[dict]:
        """Holt offene Aufgaben der ganzen Firma (DG) oder des Teams (Manager)."""
        from app.models.action import Assignment
        from sqlalchemy.orm import selectinload
        
        query = (
            select(Action)
            .join(Assignment)
            .options(selectinload(Action.assignments).selectinload(Assignment.user))
            .where(
                Action.client_id == client_id,
                Action.status == "PENDING"
            )
        )

        if role == "manager":
            # 1. Teammitglieder finden
            team_query = select(UserModel.id).where(
                UserModel.manager_id == manager_id,
                UserModel.client_id == client_id # Defense in depth
            )
            team_res = await self.db.execute(team_query)
            team_ids = [row[0] for row in team_res.all()]
            team_ids.append(manager_id)
            query = query.where(Assignment.user_id.in_(team_ids))

        query = (
            query
            .order_by(Action.priority.desc(), Action.due_date.asc().nulls_last())
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        actions = result.scalars().all()
        return [
            {
                "id": a.id,
                "title": a.title,
                "due_date": a.due_date.isoformat() if a.due_date else None,
                "priority": a.priority,
                "assigned_to": a.assigned_to
            } for a in actions
        ]

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
                Action.status == "PENDING",
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
