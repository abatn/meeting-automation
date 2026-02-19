from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_db, get_current_active_superuser, get_current_user
from backend.app.schemas.audit import AuditLog
from backend.app.services.audit_service import audit_service
from backend.app.models.user import User, UserRole
from starlette.responses import StreamingResponse
import io

router = APIRouter()

@router.get("/", response_model=List[AuditLog])
async def read_audit_logs(
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[int] = None,
    event_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve audit logs. Requires ADMIN role or SUPERUSER status.
    """
    if current_user.role != UserRole.ADMIN and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    audit_logs = await audit_service.get_audit_logs(
        db,
        skip=skip,
        limit=limit,
        user_id=user_id,
        action_type=event_type,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date
    )
    return audit_logs

@router.get("/{log_id}", response_model=AuditLog)
async def read_audit_log_by_id(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve a specific audit log by ID. Requires ADMIN role or SUPERUSER status.
    """
    if current_user.role != UserRole.ADMIN and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # We need to implement get_audit_log_by_id in AuditService or just query it here
    # Since AuditService doesn't have get_audit_log_by_id, let's use get_audit_logs with limit 1 and filter by ID if possible,
    # or just add a method to AuditService.
    # But wait, AuditService.get_audit_logs doesn't filter by ID.
    # Let's add get_audit_log to AuditService first.
    
    # For now, let's implement it directly here using select
    from sqlalchemy import select
    from backend.app.models.audit_log import AuditLog as AuditLogModel
    
    result = await db.execute(select(AuditLogModel).filter(AuditLogModel.id == log_id))
    audit_log = result.scalars().first()
    
    if not audit_log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return audit_log

@router.get("/export", response_class=StreamingResponse)
async def export_audit_logs_to_csv(
    user_id: Optional[int] = None,
    event_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser) # Only superusers can export
):
    """
    Export audit logs to a CSV file. Requires SUPERUSER status.
    """
    # The get_current_active_superuser dependency already handles permission checks.

    csv_data = await audit_service.export_audit_logs(
        db,
        file_format="csv",
        user_id=user_id,
        action_type=event_type,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date
    )
    
    # Create a file-like object in memory
    output = io.StringIO()
    output.write(csv_data)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"}
    )
