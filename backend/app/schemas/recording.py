from pydantic import BaseModel

class RecordingBase(BaseModel):
    pass

class RecordingCreate(RecordingBase):
    pass

class Recording(RecordingBase):
    id: int

    class Config:
        orm_mode = True