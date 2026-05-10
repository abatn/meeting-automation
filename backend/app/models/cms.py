from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Column, String, Integer, Boolean, Text, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base

if TYPE_CHECKING:
    pass


class LandingSection(Base):
    __tablename__ = "landing_sections"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    section_key: Mapped[str] = mapped_column(String, unique=True, index=True)
    title: Mapped[dict] = mapped_column(JSON)
    subtitle: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    content: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cta_text: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    cta_link: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Feature(Base):
    __tablename__ = "features"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    icon: Mapped[str] = mapped_column(String)
    title: Mapped[dict] = mapped_column(JSON)
    description: Mapped[dict] = mapped_column(JSON)
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PricingPlan(Base):
    __tablename__ = "pricing_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[dict] = mapped_column(JSON)
    # plan_code links to SubscriptionPlan enum: GRATUIT, PRO, ENTREPRISE
    plan_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    price_monthly: Mapped[int] = mapped_column(Integer)
    price_yearly: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # minutes_included for this plan (replaces hardcoded values)
    minutes_included: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    features: Mapped[list] = mapped_column(JSON)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_popular: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FAQ(Base):
    __tablename__ = "faqs"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    question: Mapped[dict] = mapped_column(JSON)
    answer: Mapped[dict] = mapped_column(JSON)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Testimonial(Base):
    __tablename__ = "testimonials"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    author_name: Mapped[str] = mapped_column(String)
    author_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    content: Mapped[dict] = mapped_column(JSON)
    avatar_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rating: Mapped[int] = mapped_column(Integer, default=5)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())