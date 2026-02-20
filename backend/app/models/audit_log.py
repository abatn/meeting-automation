import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    # TODO: Add other audit log fields