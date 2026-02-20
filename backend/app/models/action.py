import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.core.database import Base

class Action(Base):
    __tablename__ = "actions"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    # TODO: Add other action fields