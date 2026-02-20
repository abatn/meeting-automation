import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.core.database import Base

class Transcription(Base):
    __tablename__ = "transcriptions"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    # TODO: Add other transcription fields