from pydantic import BaseModel

class MeetingBase(BaseModel):
    pass

class MeetingCreate(MeetingBase):
    pass

class Meeting(MeetingBase):
    id: int

    class Config:
        orm_mode = True