import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.core.database import Base

class Recording(Base):
    __tablename__ = "recordings"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    # TODO: Add other recording fields