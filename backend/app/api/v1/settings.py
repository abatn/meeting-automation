from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.models.user import User as UserModel
from app.models.setting import BrandingSettings as BrandingModel
from app.schemas.setting import BrandingSettings, BrandingSettingsCreate, BrandingSettingsUpdate

router = APIRouter()

@router.get("/branding", response_model=BrandingSettings)
async def get_branding_settings(
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieves the currently active custom branding configuration.
    """
    stmt = select(BrandingModel).where(BrandingModel.is_active == True)
    result = await db.execute(stmt)
    branding = result.scalars().first()

    # Fallback default empty configuration if nothing is configured
    if not branding:
        return BrandingSettings(
            id="default",
            organization_name="",
            logo_url="",
            header_text="",
            footer_text="",
            default_watermark=False,
            is_active=True,
            created_at="2026-01-01T00:00:00"
        )

    return branding

@router.post("/branding", response_model=BrandingSettings)
async def create_or_update_branding_settings(
    branding_in: BrandingSettingsCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Creates or overrides the active custom branding settings (Only 1 active setting is maintained).
    Requires audit logging via middleware automatically.
    """
    # Disable previously active settings
    stmt = select(BrandingModel).where(BrandingModel.is_active == True)
    result = await db.execute(stmt)
    existing_branding = result.scalars().first()

    if existing_branding:
        existing_branding.is_active = False
        db.add(existing_branding)

    # Create new active branding setting
    new_branding = BrandingModel(
        id=str(uuid.uuid4()),
        organization_name=branding_in.organization_name,
        logo_url=branding_in.logo_url,
        header_text=branding_in.header_text,
        footer_text=branding_in.footer_text,
        default_watermark=branding_in.default_watermark,
        is_active=True
    )

    db.add(new_branding)
    await db.commit()
    await db.refresh(new_branding)

    return new_branding
