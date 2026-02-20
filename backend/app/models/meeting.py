import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.core.database import Base

class Meeting(Base):
    __tablename__ = "meetings"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    # TODO: Add other meeting fields