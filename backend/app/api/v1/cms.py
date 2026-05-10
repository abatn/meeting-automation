"""
CMS API for Landing Page content.
Note: CMS is platform-wide (not tenant-specific) - only system_admin can modify.
Multi-Tenant compliant: Public endpoints for all, Admin endpoints for system_admin only.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api import deps
from app.models import cms as cms_models
from app.schemas import cms as cms_schemas
from app.models.user import User, UserRole

router = APIRouter()

SUPPORTED_LANGUAGES = ["en", "fr-TN", "ar-TN"]


def get_translation(data: dict, lang: str) -> str:
    """Get translation for a specific language from JSON data."""
    if not data:
        return ""
    return data.get(lang, data.get("en", ""))


@router.get("/landing", response_model=cms_schemas.LandingContentResponse)
async def get_landing_content(
    lang: str = Query("en", pattern="^(en|fr-TN|ar-TN)$"),
    db: AsyncSession = Depends(deps.get_db),
) -> cms_schemas.LandingContentResponse:
    """Get all landing page content for a specific language."""
    # Get active sections
    stmt_sections = select(cms_models.LandingSection).where(cms_models.LandingSection.is_active == True).order_by(cms_models.LandingSection.order)
    result_sections = await db.execute(stmt_sections)
    sections = result_sections.scalars().all()

    # Get active features
    stmt_features = select(cms_models.Feature).where(cms_models.Feature.is_active == True).order_by(cms_models.Feature.order)
    result_features = await db.execute(stmt_features)
    features = result_features.scalars().all()

    # Get active pricing plans
    stmt_pricing = select(cms_models.PricingPlan).where(cms_models.PricingPlan.is_active == True).order_by(cms_models.PricingPlan.order)
    result_pricing = await db.execute(stmt_pricing)
    pricing = result_pricing.scalars().all()

    # Get active FAQs
    stmt_faqs = select(cms_models.FAQ).where(cms_models.FAQ.is_active == True).order_by(cms_models.FAQ.order)
    result_faqs = await db.execute(stmt_faqs)
    faqs = result_faqs.scalars().all()

    return cms_schemas.LandingContentResponse(
        sections=sections,
        features=features,
        pricing=pricing,
        faqs=faqs
    )


@router.get("/features", response_model=List[cms_schemas.Feature])
async def get_features(
    lang: str = Query("en", pattern="^(en|fr-TN|ar-TN)$"),
    db: AsyncSession = Depends(deps.get_db),
) -> List[cms_schemas.Feature]:
    """Get all active features."""
    stmt = select(cms_models.Feature).where(cms_models.Feature.is_active == True).order_by(cms_models.Feature.order)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/pricing", response_model=List[cms_schemas.PricingPlan])
async def get_pricing(
    lang: str = Query("en", pattern="^(en|fr-TN|ar-TN)$"),
    db: AsyncSession = Depends(deps.get_db),
) -> List[cms_schemas.PricingPlan]:
    """Get all active pricing plans."""
    stmt = select(cms_models.PricingPlan).where(cms_models.PricingPlan.is_active == True).order_by(cms_models.PricingPlan.order)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/faq", response_model=List[cms_schemas.FAQ])
async def get_faqs(
    lang: str = Query("en", pattern="^(en|fr-TN|ar-TN)$"),
    db: AsyncSession = Depends(deps.get_db),
) -> List[cms_schemas.FAQ]:
    """Get all active FAQs."""
    stmt = select(cms_models.FAQ).where(cms_models.FAQ.is_active == True).order_by(cms_models.FAQ.order)
    result = await db.execute(stmt)
    return result.scalars().all()


# Admin endpoints (system_admin only - CMS is platform-wide, not tenant-specific)
@router.post("/sections", response_model=cms_schemas.LandingSection)
async def create_section(
    section_in: cms_schemas.LandingSectionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_system_admin),
) -> cms_schemas.LandingSection:
    """Create a new landing section (admin only)."""
    from uuid import uuid4
    section = cms_models.LandingSection(id=str(uuid4()), **section_in.dict())
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section


@router.put("/sections/{section_id}", response_model=cms_schemas.LandingSection)
async def update_section(
    section_id: str,
    section_in: cms_schemas.LandingSectionUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_system_admin),
) -> cms_schemas.LandingSection:
    """Update a landing section (admin only)."""
    stmt = select(cms_models.LandingSection).where(cms_models.LandingSection.id == section_id)
    result = await db.execute(stmt)
    section = result.scalar_one_or_none()
    
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    for key, value in section_in.dict(exclude_unset=True).items():
        setattr(section, key, value)
    
    await db.commit()
    await db.refresh(section)
    return section


@router.post("/features", response_model=cms_schemas.Feature)
async def create_feature(
    feature_in: cms_schemas.FeatureCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_system_admin),
) -> cms_schemas.Feature:
    """Create a new feature (admin only)."""
    from uuid import uuid4
    feature = cms_models.Feature(id=str(uuid4()), **feature_in.dict())
    db.add(feature)
    await db.commit()
    await db.refresh(feature)
    return feature


@router.put("/features/{feature_id}", response_model=cms_schemas.Feature)
async def update_feature(
    feature_id: str,
    feature_in: cms_schemas.FeatureUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_system_admin),
) -> cms_schemas.Feature:
    """Update a feature (admin only)."""
    stmt = select(cms_models.Feature).where(cms_models.Feature.id == feature_id)
    result = await db.execute(stmt)
    feature = result.scalar_one_or_none()
    
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    for key, value in feature_in.dict(exclude_unset=True).items():
        setattr(feature, key, value)
    
    await db.commit()
    await db.refresh(feature)
    return feature


@router.post("/pricing", response_model=cms_schemas.PricingPlan)
async def create_pricing_plan(
    plan_in: cms_schemas.PricingPlanCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_system_admin),
) -> cms_schemas.PricingPlan:
    """Create a new pricing plan (admin only)."""
    from uuid import uuid4
    plan = cms_models.PricingPlan(id=str(uuid4()), **plan_in.dict())
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


@router.put("/pricing/{plan_id}", response_model=cms_schemas.PricingPlan)
async def update_pricing_plan(
    plan_id: str,
    plan_in: cms_schemas.PricingPlanUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_system_admin),
) -> cms_schemas.PricingPlan:
    """Update a pricing plan (admin only)."""
    stmt = select(cms_models.PricingPlan).where(cms_models.PricingPlan.id == plan_id)
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Pricing plan not found")
    
    for key, value in plan_in.dict(exclude_unset=True).items():
        setattr(plan, key, value)
    
    await db.commit()
    await db.refresh(plan)
    return plan


@router.post("/faq", response_model=cms_schemas.FAQ)
async def create_faq(
    faq_in: cms_schemas.FAQCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_system_admin),
) -> cms_schemas.FAQ:
    """Create a new FAQ (admin only)."""
    from uuid import uuid4
    faq = cms_models.FAQ(id=str(uuid4()), **faq_in.dict())
    db.add(faq)
    await db.commit()
    await db.refresh(faq)
    return faq


@router.put("/faq/{faq_id}", response_model=cms_schemas.FAQ)
async def update_faq(
    faq_id: str,
    faq_in: cms_schemas.FAQUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_system_admin),
) -> cms_schemas.FAQ:
    """Update an FAQ (admin only)."""
    stmt = select(cms_models.FAQ).where(cms_models.FAQ.id == faq_id)
    result = await db.execute(stmt)
    faq = result.scalar_one_or_none()
    
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    for key, value in faq_in.dict(exclude_unset=True).items():
        setattr(faq, key, value)
    
    await db.commit()
    await db.refresh(faq)
    return faq
