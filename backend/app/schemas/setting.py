from typing import Optional
from pydantic import BaseModel
from datetime import datetime

class BrandingSettingsBase(BaseModel):
    organization_name: Optional[str] = None
    logo_url: Optional[str] = None
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    default_watermark: Optional[bool] = False
    is_active: Optional[bool] = True

class BrandingSettingsCreate(BrandingSettingsBase):
    pass

class BrandingSettingsUpdate(BrandingSettingsBase):
    pass

class BrandingSettings(BrandingSettingsBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
