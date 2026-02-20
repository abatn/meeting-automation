from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from app.models.audit_log import AuditLog
from app.core.database import SessionLocal
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Skip logging for non-API routes
        if not request.url.path.startswith("/api"):
            return response

        # Get user from request state if available (set by auth dependency)
        user_id = getattr(request.state, "user_id", None)

        # Read request body
        request_body = await request.body()
        
        # Read response body
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        
        # Log to database
        db = SessionLocal()
        try:
            audit_log = AuditLog(
                user_id=user_id,
                method=request.method,
                path=request.url.path,
                query_params=str(request.query_params),
                request_body=request_body.decode('utf-8', errors='ignore'),
                status_code=response.status_code,
                response_body=response_body.decode('utf-8', errors='ignore'),
                timestamp=datetime.utcnow()
            )
            db.add(audit_log)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log audit trail: {e}")
            db.rollback()
        finally:
            db.close()
        
        # Re-create response so it can be returned
        return response.__class__(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )