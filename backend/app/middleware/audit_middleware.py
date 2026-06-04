import logging
import uuid
from typing import Callable, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError

from app.models.audit_log import AuditLog
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
        """Write audit entry using a dedicated DB session (ISO 27001 compliant).

        Uses its own AsyncSessionLocal() session because the request-scoped
        session from get_db is already closed by the time this method runs
        (call_next completes the full FastAPI lifecycle including dependency cleanup).
        """
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.user import User
        from app.models.client import Client

        async with AsyncSessionLocal() as db:
            try:
                valid_user_id = None
                if user_id:
                    user_exists = await db.execute(
                        select(User.id).where(User.id == user_id).where(User.client_id == client_id)
                    )
                    if user_exists.scalar_one_or_none():
                        valid_user_id = user_id

                # Determine record_id from path parameters
                record_id = None
                for key in ["action_id", "meeting_id", "recording_id", "transcription_id", "pv_id", "user_id", "client_id", "room_id"]:
                    if key in request.path_params:
                        record_id = request.path_params[key]
                        break

                # Determine table_name from path
                path = request.url.path
                parts = [p for p in path.split("/") if p]
                table_name = "root"
                if "api" in parts:
                    api_idx = parts.index("api")
                    if len(parts) > api_idx + 2:
                        table_name = parts[api_idx + 2]
                    elif len(parts) > api_idx + 1:
                        table_name = parts[api_idx + 1]
                elif parts:
                    table_name = parts[0]

                # VALIDATE client_id exists before writing audit log
                client_check = await db.execute(select(Client.id).where(Client.id == client_id))
                if not client_check.scalar_one_or_none():
                    logging.warning(f"AuditMiddleware: client_id {client_id} not found, skipping audit")
                    return

                audit_entry = AuditLog(
                    id=str(uuid.uuid4()),
                    client_id=client_id,
                    user_id=valid_user_id,
                    action=request.method,
                    table_name=table_name,
                    record_id=record_id,
                    ip_address=request.client.host if request.client else "unknown",
                    user_agent=request.headers.get("user-agent", "unknown"),
                )

                # For actions, capture the new state after the change
                if table_name == "actions" and record_id and request.method in ("POST", "PUT", "PATCH"):
                    try:
                        from app.models.action import Action as ActionModel
                        result = await db.execute(select(ActionModel).where(ActionModel.id == record_id))
                        new_action = result.scalar_one_or_none()
                        if new_action:
                            audit_entry.new_values = {
                                "status": new_action.status.value if hasattr(new_action.status, 'value') else str(new_action.status)
                            }
                    except Exception as e:
                        logging.warning(f"Failed to capture new state for audit: {e}")

                if not valid_user_id and user_id:
                    audit_entry.new_values = {"stale_user_id": user_id}

                db.add(audit_entry)
                await db.commit()
                logging.info(f"Audit log created: {audit_entry.action} on {table_name}")
            except Exception as e:
                logging.error(f"Audit log failed: {e}", exc_info=True)
                try:
                    await db.rollback()
                except Exception:
                    pass
