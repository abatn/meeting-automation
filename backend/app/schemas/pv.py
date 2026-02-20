from pydantic import BaseModel

class PVBase(BaseModel):
    pass

class PVCreate(PVBase):
    pass

class PV(PVBase):
    id: int

    class Config:
        orm_mode = True