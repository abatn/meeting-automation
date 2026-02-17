import time
import json
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
from typing import Dict, Any, Optional

from backend.app.core.database import SessionLocal
from backend.app.services.audit_service import AuditService
from backend.app.schemas.audit import AuditLogCreate
from backend.app.api.deps import get_current_user_from_token_sync
from backend.app.core.config import settings
from backend.app.core.database import get_db_session_sync # Import the synchronous session getter

class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.audit_service = AuditService()
        self.SENSITIVE_PATHS = ["/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/password-reset"]
        self.SENSITIVE_FIELDS = ["password", "old_password", "new_password", "token"]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.time()
        
        user_id: Optional[int] = None
        try:
            # Attempt to get the current user from the token in the request headers
            token = request.headers.get("Authorization")
            if token and token.startswith("Bearer "):
                token = token.split(" ")[1]
                
                # Get a synchronous DB session for the middleware
                with get_db_session_sync() as db_session:
                    current_user = get_current_user_from_token_sync(db_session, token)
                    if current_user:
                        user_id = current_user.id
        except Exception:
            user_id = None # No authenticated user or token validation failed

        # Mask sensitive data from request body if present and path is sensitive
        request_body_masked: Optional[Dict[str, Any]] = None
        if request.method in ["POST", "PUT"] and request.url.path in self.SENSITIVE_PATHS:
            try:
                # Read request body once, then reconstruct it for the next middleware/endpoint
                body = await request.json()
                request_body_masked = self._mask_sensitive_data(body)
                # Reconstruct the request body for the actual endpoint
                request._body = json.dumps(body).encode('utf-8')
            except json.JSONDecodeError:
                pass # Not a JSON body, or empty

        try:
            response = await call_next(request)
        except Exception as e:
            status_code = 500
            raise e
        else:
            status_code = response.status_code
        
        process_time = time.time() - start_time

        # Mask sensitive data from response body if present and path is sensitive
        response_body_masked: Optional[Dict[str, Any]] = None
        if request.url.path in self.SENSITIVE_PATHS and "content-type" in response.headers and "application/json" in response.headers["content-type"]:
            try:
                # Read response body
                response_body = [segment async for segment in response.body_iterator]
                response_body_str = b"".join(response_body).decode("utf-8")
                response_json = json.loads(response_body_str)
                response_body_masked = self._mask_sensitive_data(response_json)
                
                # Recreate the response with the original body
                response = Response(content=response_body_str, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)
            except json.JSONDecodeError:
                pass # Not a JSON body, or empty

        log_data = AuditLogCreate(
            user_id=user_id,
            action=self._determine_action_type(request.method, request.url.path),
            method=request.method,
            path=str(request.url),
            resource_type=self._determine_resource_type(request.url.path),
            resource_id=self._extract_resource_id(request.url.path),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            status_code=status_code,
            duration=process_time,
            details={
                "request_body": request_body_masked,
                "response_body": response_body_masked,
                "query_params": dict(request.query_params)
            }
        )


        return response

    def _mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Masks sensitive fields in a dictionary."""
        masked_data = data.copy()
        for field in self.SENSITIVE_FIELDS:
            if field in masked_data:
                masked_data[field] = "****MASKED****"
        return masked_data

    def _determine_action_type(self, method: str, path: str) -> str:
        """Determines the action type based on method and path."""
        if path == "/api/v1/auth/login":
            return "LOGIN"
        if path == "/api/v1/auth/register":
            return "REGISTER"
        if path == "/api/v1/auth/password-reset":
            return "PASSWORD_RESET"
        
        # Generic actions
        if method == "POST":
            return "CREATE"
        if method == "GET":
            return "READ"
        if method == "PUT":
            return "UPDATE"
        if method == "DELETE":
            return "DELETE"
        return "UNKNOWN"

    def _determine_resource_type(self, path: str) -> Optional[str]:
        """Determines the resource type from the path."""
        parts = path.split('/')
        if "api" in parts and "v1" in parts:
            try:
                # Find the part after 'v1' that is not an ID
                v1_index = parts.index("v1")
                if v1_index + 1 < len(parts):
                    resource_candidate = parts[v1_index + 1]
                    # Basic check to see if it's likely a resource name (not an ID)
                    if not resource_candidate.isdigit() and resource_candidate not in ["auth", "docs", "openapi.json"]:
                        return resource_candidate.capitalize()
            except ValueError:
                pass
        return None

    def _extract_resource_id(self, path: str) -> Optional[int]:
        """Extracts resource ID from the path if present."""
        parts = path.split('/')
        for part in parts:
            if part.isdigit():
                return int(part)
        return None