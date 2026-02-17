from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, delete
import csv
import json
from enum import Enum

from backend.app.models.audit_log import AuditLog
from backend.app.schemas.audit import AuditLogCreate, AuditLog as AuditLogSchema
from sqlalchemy.ext.asyncio import AsyncSession


class AuditAction(str, Enum):
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    REGISTER = "REGISTER"
    GENERATE_PV = "GENERATE_PV"
    VALIDATE_PV = "VALIDATE_PV"
    EXTRACT_DECISIONS = "EXTRACT_DECISIONS"
    EXTRACT_ACTION_POINTS = "EXTRACT_ACTION_POINTS"
    GET_PV = "GET_PV"
    # Add other actions as needed


class AuditService:
    async def log_action(self, db: AsyncSession, log_data: AuditLogCreate) -> AuditLog:
        """
        Logs an audit action to the database.
        """
        db_audit_log = AuditLog(**log_data.dict())
        db.add(db_audit_log)
        await db.commit()
        await db.refresh(db_audit_log)
        return db_audit_log

    async def get_audit_logs(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        action_type: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        method: Optional[str] = None,
        status_code: Optional[int] = None,
        order_by: str = "timestamp",
        order_direction: str = "desc"
    ) -> List[AuditLog]:
        """
        Retrieves audit logs with various filtering and sorting options.
        """
        query = select(AuditLog)

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if action_type:
            query = query.filter(AuditLog.action == action_type)
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        if ip_address:
            query = query.filter(AuditLog.ip_address == ip_address)
        if method:
            query = query.filter(AuditLog.method == method)
        if status_code:
            query = query.filter(AuditLog.status_code == status_code)

        if order_direction == "desc":
            query = query.order_by(desc(getattr(AuditLog, order_by)))
        else:
            query = query.order_by(asc(getattr(AuditLog, order_by)))

        result = await db.execute(query.offset(skip).limit(limit))
        return result.scalars().all()

    async def get_user_audit_logs(
        self, db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[AuditLog]:
        """
        Retrieves audit logs for a specific user.
        """
        return await self.get_audit_logs(db, user_id=user_id, skip=skip, limit=limit)

    async def get_resource_audit_logs(
        self, db: AsyncSession, resource_type: str, resource_id: int, skip: int = 0, limit: int = 100
    ) -> List[AuditLog]:
        """
        Retrieves audit logs for a specific resource.
        """
        query = select(AuditLog).filter(
            AuditLog.resource_type == resource_type,
            AuditLog.resource_id == resource_id
        ).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def cleanup_old_audit_logs(self, db: AsyncSession, days_to_keep: int = 365):
        """
        Deletes audit logs older than a specified number of days.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        result = await db.execute(
            delete(AuditLog).filter(AuditLog.timestamp < cutoff_date)
        )
        await db.commit()
        return result.rowcount

    async def export_audit_logs(
        self,
        db: AsyncSession,
        file_format: str = "csv",
        user_id: Optional[int] = None,
        action_type: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> str:
        """
        Exports audit logs to CSV or JSON format based on filters.
        Returns the content of the exported file as a string.
        """
        logs = await self.get_audit_logs(
            db,
            limit=None, # Get all matching logs for export
            user_id=user_id,
            action_type=action_type,
            resource_type=resource_type,
            start_date=start_date,
            end_date=end_date,
        )

        if file_format == "csv":
            output = []
            # Get field names from the Pydantic schema for consistent headers
            fieldnames = [field_name for field_name in AuditLogSchema.model_fields.keys() if field_name != 'id']
            output.append(",".join(fieldnames)) # Header row

            for log in logs:
                row = []
                for field in fieldnames:
                    value = getattr(log, field, "")
                    if isinstance(value, datetime):
                        row.append(value.isoformat())
                    elif isinstance(value, dict):
                        row.append(json.dumps(value))
                    else:
                        row.append(str(value))
                output.append(",".join(row))
            return "\n".join(output)
        elif file_format == "json":
            # Convert AuditLog objects to AuditLogSchema Pydantic models for serialization
            # Then convert Pydantic models to dictionaries and dump to JSON
            return json.dumps([AuditLogSchema.model_validate(log).model_dump() for log in logs], indent=4)
        else:
            raise ValueError("Unsupported file format. Choose 'csv' or 'json'.")
