from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class AuditLogBase(BaseModel):
    client_id: Optional[str] = None
    action: str
    table_name: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AuditLog(AuditLogBase):
    id: str
    user_id: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True
