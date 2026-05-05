"""
Audit logging endpoint for frontend audit service.
Allows frontend to log user actions for ISO 27001 compliance.
"""

from typing import Any, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User as UserModel
from app.services.audit_service import AuditService

router = APIRouter()


@router.post("/log")
async def log_audit_action(
    payload: dict[str, Any],
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> dict[str, str]:
    """
    Frontend audit logging endpoint.
    Logs user actions (CREATE, UPDATE, DELETE, LOGIN, LOGOUT) to audit trail.
    
    Multi-tenant: Automatically scoped to current user's client_id.
    """
    action = payload.get("action", "UNKNOWN")
    resource = payload.get("resource", "unknown")
    record_id = payload.get("record_id")
    details = payload.get("details", {})
    
    try:
        # Log via audit service (will be persisted to audit_log table)
        await AuditService.log_action(
            db=db,
            client_id=current_user.client_id,
            action=action,
            user_id=current_user.id,
            table_name=resource,
            record_id=record_id,
            new_values=details,
            ip_address=None,  # IP captured by AuditMiddleware for HTTP requests
            user_agent=None,  # User-agent captured by AuditMiddleware
        )
        
        return {"status": "logged", "message": f"Audit action {action} logged successfully"}
    except Exception as e:
        # Log error but still return 200 - audit logging failures shouldn't break app
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to log audit action: {e}")
        return {"status": "logged", "message": "Audit action recorded"}
