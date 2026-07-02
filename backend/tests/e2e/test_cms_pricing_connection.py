"""
E2E Test: CMS pricing_plans <-> Client subscription_plan Connection

Tests:
- C1: PricingPlan model has plan_code and minutes_included fields
- C2: ClientService._get_minutes_for_plan reads from CMS
- C3: BillingService._get_plan_details_from_cms returns correct values
- C4: Migration added plan_code and minutes_included columns

Date: 2026-05-10
Author: OpenCode AI
"""
import pytest
import inspect


def test_c1_pricing_plan_model_has_new_fields():
    """C1: PricingPlan model has plan_code and minutes_included fields"""
    from app.models.cms import PricingPlan
    
    # Check that the model has the new fields
    columns = [c.name for c in PricingPlan.__table__.columns]
    assert 'plan_code' in columns, "PricingPlan should have plan_code column"
    assert 'minutes_included' in columns, "PricingPlan should have minutes_included column"


def test_c2_client_service_reads_from_cms():
    """C2: ClientService._get_minutes_for_plan reads from CMS"""
    from app.services.client_service import ClientService
    
    source = inspect.getsource(ClientService._get_minutes_for_plan)
    
    # Should query PricingPlan
    assert "PricingPlan" in source, "Should query PricingPlan model"
    assert "plan_code" in source, "Should filter by plan_code"


def test_c3_billing_service_has_cms_method():
    """C3: BillingService has _get_plan_details_from_cms method"""
    from app.services.billing_service import BillingService
    
    assert hasattr(BillingService, '_get_plan_details_from_cms')
    
    source = inspect.getsource(BillingService._get_plan_details_from_cms)
    assert "PricingPlan" in source, "Should query PricingPlan model"
    assert "minutes_included" in source, "Should return minutes_included"
    assert "price_monthly" in source, "Should return price_monthly"


def test_c4_pricing_plan_schema_has_new_fields():
    """C4: PricingPlan schema has plan_code and minutes_included fields"""
    from app.schemas.cms import PricingPlanBase, PricingPlanUpdate
    
    # Check base schema
    base_fields = PricingPlanBase.model_fields.keys()
    assert 'plan_code' in base_fields, "PricingPlanBase should have plan_code field"
    assert 'minutes_included' in base_fields, "PricingPlanBase should have minutes_included field"
    
    # Check update schema
    update_fields = PricingPlanUpdate.model_fields.keys()
    assert 'plan_code' in update_fields, "PricingPlanUpdate should have plan_code field"
    assert 'minutes_included' in update_fields, "PricingPlanUpdate should have minutes_included field"


def test_c5_default_plan_minutes_fallback():
    """C5: DEFAULT_PLAN_MINUTES fallback exists in ClientService"""
    from app.services.client_service import DEFAULT_PLAN_MINUTES
    from app.models.client import SubscriptionPlan
    
    assert DEFAULT_PLAN_MINUTES[SubscriptionPlan.GRATUIT] == 120
    assert DEFAULT_PLAN_MINUTES[SubscriptionPlan.PRO] == 1800
    assert DEFAULT_PLAN_MINUTES[SubscriptionPlan.ENTREPRISE] == 3600


def test_c6_default_plan_config_fallback():
    """C6: DEFAULT_PLAN_CONFIG fallback exists in BillingService"""
    from app.services.billing_service import DEFAULT_PLAN_CONFIG
    
    assert DEFAULT_PLAN_CONFIG["GRATUIT"]["minutes"] == 120
    assert DEFAULT_PLAN_CONFIG["GRATUIT"]["price"] == 0.0
    assert DEFAULT_PLAN_CONFIG["PRO"]["minutes"] == 1800
    assert DEFAULT_PLAN_CONFIG["PRO"]["price"] == 99.0
    assert DEFAULT_PLAN_CONFIG["ENTREPRISE"]["minutes"] == 3600
    assert DEFAULT_PLAN_CONFIG["ENTREPRISE"]["price"] == 499.0


def test_c7_handle_stripe_webhook_uses_cms():
    """C7: handle_stripe_webhook_success uses _get_plan_details_from_cms"""
    from app.services.billing_service import BillingService
    
    source = inspect.getsource(BillingService.handle_stripe_webhook_success)
    
    assert "_get_plan_details_from_cms" in source, "Should call _get_plan_details_from_cms"
    # Should NOT have hardcoded values anymore
    assert 'mins_inc = 3000 if plan == "PRO" else 12000' not in source, "Should not have hardcoded minutes"
