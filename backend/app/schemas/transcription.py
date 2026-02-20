from pydantic import BaseModel

class TranscriptionBase(BaseModel):
    pass

class TranscriptionCreate(TranscriptionBase):
    pass

class Transcription(TranscriptionBase):
    id: int

    class Config:
        orm_mode = True