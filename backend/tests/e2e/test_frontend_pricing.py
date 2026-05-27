"""
E2E Test: Frontend BillingPanel loads prices from CMS API

Tests:
- F1: BillingPanel imports PricingPlan interface
- F2: BillingPanel has getPrice function
- F3: BillingPanel fetches from /cms/pricing API
- F4: BillingPanel uses dynamic prices instead of hardcoded

Date: 2026-05-10
Author: OpenCode AI
"""
import pytest
import os


def _get_billing_panel_path():
    """Find BillingPanel.tsx regardless of host or Docker environment."""
    candidates = []
    
    # Docker container: volume mount ./:/workspace, backend at /app
    candidates.append("/workspace/frontend/src/pages/billing/BillingPanel.tsx")
    
    # Host machine: go up 4 levels from backend/tests/e2e/
    candidates.append(os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "frontend/src/pages/billing/BillingPanel.tsx"
    ))
    
    for path in candidates:
        if os.path.exists(path):
            return path
    
    raise FileNotFoundError(f"BillingPanel.tsx not found. Tried: {candidates}")


def test_f1_billing_panel_has_pricing_interface():
    """F1: BillingPanel has PricingPlan interface"""
    billing_panel_path = _get_billing_panel_path()
    
    with open(billing_panel_path, 'r') as f:
        content = f.read()
    
    assert "interface PricingPlan" in content, "BillingPanel should have PricingPlan interface"
    assert "plan_code" in content, "PricingPlan interface should have plan_code field"


def test_f2_billing_panel_has_get_price_function():
    """F2: BillingPanel has getPrice function"""
    billing_panel_path = _get_billing_panel_path()
    
    with open(billing_panel_path, 'r') as f:
        content = f.read()
    
    assert "getPrice" in content, "BillingPanel should have getPrice function"
    assert "FALLBACK_PRICES" in content, "BillingPanel should have FALLBACK_PRICES"


def test_f3_billing_panel_fetches_cms_pricing():
    """F3: BillingPanel fetches from /cms/pricing API"""
    billing_panel_path = _get_billing_panel_path()
    
    with open(billing_panel_path, 'r') as f:
        content = f.read()
    
    assert "/cms/pricing" in content, "BillingPanel should fetch from /cms/pricing"
    assert "setPricingPlans" in content, "BillingPanel should set pricingPlans state"


def test_f4_billing_panel_uses_dynamic_prices():
    """F4: BillingPanel uses getPrice() instead of hardcoded values"""
    billing_panel_path = _get_billing_panel_path()
    
    with open(billing_panel_path, 'r') as f:
        content = f.read()
    
    # Should use dynamic prices
    assert "getPrice('PRO')" in content, "Should use getPrice('PRO') for PRO price"
    assert "getPrice('ENTREPRISE')" in content, "Should use getPrice('ENTREPRISE') for Enterprise price"
    
    # Should NOT have hardcoded prices in the display
    lines = content.split('\n')
    display_lines = [l for l in lines if 'Typography variant="h3"' in l and '$' in l]
    for line in display_lines:
        assert '$99' not in line or 'getPrice' in line, "Should not have hardcoded $99 in display"
        assert '$499' not in line or 'getPrice' in line, "Should not have hardcoded $499 in display"
