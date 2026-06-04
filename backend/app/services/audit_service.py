import uuid
import logging
from typing import Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

class AuditService:
    @staticmethod
    async def log_action(
        db: AsyncSession,
        client_id: str,
        action: str,
        user_id: Optional[str] = None,
        table_name: Optional[str] = None,
        record_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = "system",
        user_agent: Optional[str] = "internal-service"
    ):
        """
        Creates an audit log entry for security and compliance (ISO 27001).
        """
        try:
            audit_entry = AuditLog(
                id=str(uuid.uuid4()),
                client_id=client_id,
                user_id=user_id,
                action=action,
                table_name=table_name,
                record_id=record_id,
                old_values=old_values,
                new_values=new_values,
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.add(audit_entry)
            await db.commit()
            logger.info(f"Audit log created: {action} on {table_name or 'unknown'}")
            return audit_entry
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            try:
                await db.rollback()
            except Exception:
                pass
            # We don't raise here to prevent breaking the main flow, 
            # but in production you might want strict audit.
            return None
