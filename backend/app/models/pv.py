import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.core.database import Base

class PV(Base):
    __tablename__ = "pvs"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    # TODO: Add other PV fields