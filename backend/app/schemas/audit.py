from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class AuditLogBase(BaseModel):
    user_id: Optional[int] = Field(None, description="ID of the user who performed the action")
    action: str = Field(..., description="Type of action performed (e.g., 'LOGIN', 'CREATE_MEETING')")
    method: str = Field(..., description="HTTP method of the request (e.g., GET, POST)")
    path: str = Field(..., description="Request path")
    resource_type: Optional[str] = Field(None, description="Type of resource affected (e.g., 'Meeting', 'User')")
    resource_id: Optional[int] = Field(None, description="ID of the resource affected")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the action")
    ip_address: Optional[str] = Field(None, description="IP address from which the action originated")
    user_agent: Optional[str] = Field(None, description="User-Agent string of the client")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details about the action")
    status_code: Optional[int] = Field(None, description="HTTP status code of the response")
    duration: Optional[float] = Field(None, description="Duration of the request in seconds")

class AuditLogCreate(AuditLogBase):
    class Config:
        extra = 'ignore'

class AuditLog(AuditLogBase):
    id: int

    class Config:
        from_attributes = True