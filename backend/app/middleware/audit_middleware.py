from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
import time
import json
import uuid
from typing import Callable

from app.api import deps
from app.models.audit_log import AuditLog
from app.core.database import AsyncSessionLocal

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        # Only audit state-changing requests
        if request.method not in ["POST", "PUT", "PATCH", "DELETE"]:
            return await call_next(request)

        # Process request
        response = await call_next(request)

        # Log after response (simplified for now)
        # In a real scenario, we would extract user_id from token
        # and more details from request body/response
        
        # Note: Audit logging should ideally be async or offloaded to a task
        # This is a simplified implementation for the middleware structure
        async with AsyncSessionLocal() as db:
            try:
                audit_entry = AuditLog(
                    id=str(uuid.uuid4()),
                    action=request.method,
                    table_name=request.url.path.split("/")[-1],
                    ip_address=request.client.host if request.client else "unknown",
                    user_agent=request.headers.get("user-agent", "unknown")
                )
                db.add(audit_entry)
                await db.commit()
            except Exception:
                await db.rollback()

        return response
