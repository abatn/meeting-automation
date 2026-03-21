import logging
import uuid
from typing import Callable, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError

from app.models.audit_log import AuditLog
from app.core.database import AsyncSessionLocal
from app.core.config import settings


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path
        if (
            request.method not in ["POST", "PUT", "PATCH", "DELETE"]
            or "/recordings/upload" in path  # noqa: W503
        ):
            return await call_next(request)

        user_id, client_id = self._get_token_data(request)
        response = await call_next(request)
        
        if client_id:
            await self._log_audit(request, user_id, client_id)

        return response

    def _get_token_data(self, request: Request) -> tuple[Optional[str], Optional[str]]:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None, None
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            sub = payload.get("sub")
            client_id = payload.get("client_id")
            return str(sub) if sub else None, str(client_id) if client_id else None
        except JWTError:
            return None, None

    async def _log_audit(self, request: Request, user_id: Optional[str], client_id: str):
        try:
            async with AsyncSessionLocal() as db:
                valid_user_id = None
                if user_id:
                    from sqlalchemy import select
                    from app.models.user import User

                    user_exists = await db.execute(
                        select(User.id).where(User.id == user_id).where(User.client_id == client_id)
                    )
                    if user_exists.scalar_one_or_none():
                        valid_user_id = user_id

                audit_entry = AuditLog(
                    id=str(uuid.uuid4()),
                    client_id=client_id,
                    user_id=valid_user_id,
                    action=request.method,
                    table_name=request.url.path.strip("/").split("/")[-1] or "root",
                    ip_address=request.client.host if request.client else "unknown",
                    user_agent=request.headers.get("user-agent", "unknown"),
                )

                if not valid_user_id and user_id:
                    audit_entry.new_values = {"stale_user_id": user_id}

                db.add(audit_entry)
                await db.commit()
        except Exception:
            logging.error("Audit log failed (silenced)")
