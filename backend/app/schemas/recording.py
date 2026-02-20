from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

class ChunkBase(BaseModel):
    chunk_index: int
    file_path: str
    start_time: float
    end_time: float

class Chunk(ChunkBase):
    id: str
    recording_id: str

    class Config:
        from_attributes = True

class RecordingBase(BaseModel):
    meeting_id: str
    file_path: str
    file_size: Optional[int] = None
    duration: Optional[float] = None
    format: Optional[str] = None

class RecordingCreate(RecordingBase):
    pass

class Recording(RecordingBase):
    id: str
    created_at: datetime
    chunks: List[Chunk] = []

    class Config:
        from_attributes = True