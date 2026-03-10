from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class SectionBase(BaseModel):
    title: str
    content: Optional[str] = None
    order: Optional[int] = 0
    type: Optional[str] = None


class SectionCreate(SectionBase):
    pass


class Section(SectionBase):
    id: str
    pv_id: str

    class Config:
        from_attributes = True


class PVBase(BaseModel):
    meeting_id: str
    title: str
    content_html: Optional[str] = None
    status: Optional[str] = "draft"
    is_validated: Optional[bool] = False


class PVCreate(PVBase):
    sections: Optional[List[SectionCreate]] = []


class PVUpdate(BaseModel):
    title: Optional[str] = None
    content_html: Optional[str] = None
    status: Optional[str] = None
    is_validated: Optional[bool] = None


class PV(PVBase):
    id: str
    validated_by_id: Optional[str] = None
    validated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    sections: List[Section] = []

    class Config:
        from_attributes = True


class PVVersionBase(BaseModel):
    pv_id: str
    version_number: int
    change_summary: Optional[str] = None


class PVVersionCreate(PVVersionBase):
    snapshot_data: str


class PVVersion(PVVersionBase):
    id: str
    snapshot_data: str
    created_at: datetime
    created_by_id: Optional[str] = None

    class Config:
        from_attributes = True

