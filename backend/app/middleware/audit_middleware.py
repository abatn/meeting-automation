import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import time
import json
import uuid
from datetime import datetime
from typing import Callable

from app.api import deps
from app.models.audit_log import AuditLog
from app.core.database import AsyncSessionLocal
from app.core.config import settings

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        # 1. Skip auditing for non-modifying requests OR heavy file uploads
        if request.method not in ["POST", "PUT", "PATCH", "DELETE"] or "/recordings/upload" in request.url.path:
            return await call_next(request)

        # 2. Extract user_id from JWT if present
        user_id = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                user_id = payload.get("sub")
            except JWTError:
                pass

        # 3. Process request first to avoid blocking the main flow
        response = await call_next(request)

        # 4. Perform audit logging after response is ready (Non-blocking DB op)
        try:
            async with AsyncSessionLocal() as db:
                # Validate user_id exists if it's not None
                valid_user_id = None
                invalid_id_note = None
                
                if user_id:
                    from sqlalchemy import select
                    from app.models.user import User
                    user_exists = await db.execute(select(User.id).where(User.id == user_id))
                    if user_exists.scalar_one_or_none():
                        valid_user_id = user_id
                    else:
                        invalid_id_note = user_id

                audit_entry = AuditLog(
                    id=str(uuid.uuid4()),
                    user_id=valid_user_id,
                    action=request.method,
                    table_name=request.url.path.strip('/').split("/")[-1] or "root",
                    ip_address=request.client.host if request.client else "unknown",
                    user_agent=request.headers.get("user-agent", "unknown")
                )
                
                # Metadata for anonymous or stale sessions
                meta = {}
                if not valid_user_id:
                    meta["identity"] = "anonymous"
                    if invalid_id_note:
                        meta["stale_user_id"] = invalid_id_note
                
                if meta:
                    audit_entry.new_values = meta
                
                db.add(audit_entry)
                await db.commit()
        except Exception:
            logging.error("Audit log failed but was silenced to prevent request failure")

        return response
