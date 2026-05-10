from typing import Optional, List
from pydantic import BaseModel


class LandingSectionBase(BaseModel):
    section_key: str
    title: dict
    subtitle: Optional[dict] = None
    content: Optional[dict] = None
    image_url: Optional[str] = None
    cta_text: Optional[dict] = None
    cta_link: Optional[str] = None
    order: int = 0
    is_active: bool = True


class LandingSectionCreate(LandingSectionBase):
    pass


class LandingSectionUpdate(BaseModel):
    title: Optional[dict] = None
    subtitle: Optional[dict] = None
    content: Optional[dict] = None
    image_url: Optional[str] = None
    cta_text: Optional[dict] = None
    cta_link: Optional[str] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None


class LandingSection(LandingSectionBase):
    id: str
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class FeatureBase(BaseModel):
    icon: str
    title: dict
    description: dict
    order: int = 0
    is_active: bool = True


class FeatureCreate(FeatureBase):
    pass


class FeatureUpdate(BaseModel):
    icon: Optional[str] = None
    title: Optional[dict] = None
    description: Optional[dict] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None


class Feature(FeatureBase):
    id: str

    class Config:
        from_attributes = True


class PricingPlanBase(BaseModel):
    name: dict
    # plan_code links to SubscriptionPlan enum: GRATUIT, PRO, ENTREPRISE
    plan_code: Optional[str] = None
    price_monthly: int
    price_yearly: Optional[int] = None
    # minutes_included for this plan
    minutes_included: Optional[int] = None
    features: list
    stripe_price_id: Optional[str] = None
    is_popular: bool = False
    order: int = 0
    is_active: bool = True


class PricingPlanCreate(PricingPlanBase):
    pass


class PricingPlanUpdate(BaseModel):
    name: Optional[dict] = None
    plan_code: Optional[str] = None
    price_monthly: Optional[int] = None
    price_yearly: Optional[int] = None
    minutes_included: Optional[int] = None
    features: Optional[list] = None
    stripe_price_id: Optional[str] = None
    is_popular: Optional[bool] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None


class PricingPlan(PricingPlanBase):
    id: str

    class Config:
        from_attributes = True


class FAQBase(BaseModel):
    question: dict
    answer: dict
    category: Optional[str] = None
    order: int = 0
    is_active: bool = True


class FAQCreate(FAQBase):
    pass


class FAQUpdate(BaseModel):
    question: Optional[dict] = None
    answer: Optional[dict] = None
    category: Optional[str] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None


class FAQ(FAQBase):
    id: str

    class Config:
        from_attributes = True


class LandingContentResponse(BaseModel):
    sections: List[LandingSection]
    features: List[Feature]
    pricing: List[PricingPlan]
    faqs: List[FAQ]