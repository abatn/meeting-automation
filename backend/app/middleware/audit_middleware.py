import logging
import uuid
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError

from app.models.audit_log import AuditLog
from app.core.database import AsyncSessionLocal
from app.core.config import settings


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        # 1. Skip auditing for non-modifying requests OR heavy file uploads
        path = request.url.path
        if request.method not in ["POST", "PUT", "PATCH", "DELETE"] or \
           "/recordings/upload" in path:
            return await call_next(request)

        # 2. Extract user_id from JWT if present
        user_id = self._get_user_id(request)

        # 3. Process request first
        response = await call_next(request)

        # 4. Perform audit logging after response is ready
        await self._log_audit(request, user_id)

        return response

    def _get_user_id(self, request: Request) -> str:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            return payload.get("sub")
        except JWTError:
            return None

    async def _log_audit(self, request: Request, user_id: str):
        try:
            async with AsyncSessionLocal() as db:
                valid_user_id = None
                if user_id:
                    from sqlalchemy import select
                    from app.models.user import User
                    user_exists = await db.execute(
                        select(User.id).where(User.id == user_id)
                    )
                    if user_exists.scalar_one_or_none():
                        valid_user_id = user_id

                audit_entry = AuditLog(
                    id=str(uuid.uuid4()),
                    user_id=valid_user_id,
                    action=request.method,
                    table_name=request.url.path.strip('/').split("/")[-1] or "root",
                    ip_address=request.client.host if request.client else "unknown",
                    user_agent=request.headers.get("user-agent", "unknown")
                )

                if not valid_user_id and user_id:
                    audit_entry.new_values = {"stale_user_id": user_id}

                db.add(audit_entry)
                await db.commit()
        except Exception:
            logging.error("Audit log failed (silenced)")
