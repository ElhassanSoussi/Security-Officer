"""
Test suite — Feature 4: Coupon / Promo Code Support
====================================================

Validates:
  • coupon_service.py functions exist and behave correctly
  • billing.py coupon endpoints exist
  • frontend API client coupon methods
  • frontend billing page coupon UI
"""

import os
import sys
import importlib
import pytest
from unittest.mock import patch, MagicMock

# ─── Ensure imports work ─────────────────────────────────────────────────────

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND = os.path.abspath(os.path.join(ROOT, "..", "frontend"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ── 1. Service file existence ────────────────────────────────────────────────

def test_coupon_service_file_exists():
    path = os.path.join(ROOT, "app", "core", "coupon_service.py")
    assert os.path.isfile(path), "coupon_service.py must exist"


def test_coupon_service_imports():
    mod = importlib.import_module("app.core.coupon_service")
    assert hasattr(mod, "validate_coupon")
    assert hasattr(mod, "list_active_coupons")
    assert hasattr(mod, "apply_coupon_to_subscription")
    assert hasattr(mod, "get_org_discount")


# ── 2. validate_coupon ───────────────────────────────────────────────────────

def test_validate_coupon_empty_code_returns_none():
    from app.core.coupon_service import validate_coupon
    assert validate_coupon("") is None
    assert validate_coupon("   ") is None


def test_validate_coupon_none_returns_none():
    from app.core.coupon_service import validate_coupon
    # noinspection PyTypeChecker
    assert validate_coupon(None) is None


def test_validate_coupon_no_stripe_returns_none():
    from app.core.coupon_service import validate_coupon
    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""}, clear=False):
        result = validate_coupon("TESTCODE")
        assert result is None


def test_validate_coupon_strips_and_uppercases():
    """When Stripe is not available, returns None but code is processed."""
    from app.core.coupon_service import validate_coupon
    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""}, clear=False):
        result = validate_coupon("  test123  ")
    assert result is None  # No stripe, but code was processed


def test_validate_coupon_returns_dict_on_promo_match():
    """Mock a successful promo code lookup."""
    from app.core.coupon_service import validate_coupon

    mock_coupon = MagicMock()
    mock_coupon.id = "coupon_123"
    mock_coupon.percent_off = 20
    mock_coupon.amount_off = None
    mock_coupon.currency = "usd"
    mock_coupon.duration = "once"
    mock_coupon.duration_in_months = None
    mock_coupon.valid = True
    mock_coupon.name = "20% Off"

    mock_promo = MagicMock()
    mock_promo.id = "promo_123"
    mock_promo.coupon = mock_coupon

    mock_stripe = MagicMock()
    mock_stripe.PromotionCode.list.return_value = MagicMock(data=[mock_promo])

    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_123"}, clear=False):
        with patch("app.core.coupon_service._init_stripe", return_value=mock_stripe):
            result = validate_coupon("SAVE20")

    assert result is not None
    assert result["id"] == "coupon_123"
    assert result["promo_code_id"] == "promo_123"
    assert result["percent_off"] == 20
    assert result["valid"] is True
    assert result["code"] == "SAVE20"


def test_validate_coupon_fallback_to_coupon_id():
    """When promo code lookup yields nothing, try as coupon ID directly."""
    from app.core.coupon_service import validate_coupon

    mock_coupon = MagicMock()
    mock_coupon.id = "FLAT50"
    mock_coupon.percent_off = None
    mock_coupon.amount_off = 5000
    mock_coupon.currency = "usd"
    mock_coupon.duration = "forever"
    mock_coupon.duration_in_months = None
    mock_coupon.valid = True
    mock_coupon.name = "$50 Off"

    mock_stripe = MagicMock()
    mock_stripe.PromotionCode.list.return_value = MagicMock(data=[])
    mock_stripe.Coupon.retrieve.return_value = mock_coupon

    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_123"}, clear=False):
        with patch("app.core.coupon_service._init_stripe", return_value=mock_stripe):
            result = validate_coupon("FLAT50")

    assert result is not None
    assert result["amount_off"] == 5000
    assert result["promo_code_id"] is None


# ── 3. list_active_coupons ───────────────────────────────────────────────────

def test_list_active_coupons_no_stripe():
    from app.core.coupon_service import list_active_coupons
    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""}, clear=False):
        result = list_active_coupons()
    assert result == []


def test_list_active_coupons_returns_list():
    from app.core.coupon_service import list_active_coupons

    c1 = MagicMock(id="c1", name="First", percent_off=10, amount_off=None, currency="usd",
                   duration="once", duration_in_months=None, valid=True)
    c2 = MagicMock(id="c2", percent_off=None, amount_off=1000, currency="usd",
                   duration="repeating", duration_in_months=3, valid=True)
    c2.name = None  # MagicMock.name is special, set after init
    c3 = MagicMock(valid=False)  # should be excluded

    mock_stripe = MagicMock()
    mock_stripe.Coupon.list.return_value = MagicMock(data=[c1, c2, c3])

    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_123"}, clear=False):
        with patch("app.core.coupon_service._init_stripe", return_value=mock_stripe):
            result = list_active_coupons()

    assert len(result) == 2
    assert result[0]["id"] == "c1"
    assert result[1]["id"] == "c2"
    assert result[1]["name"] == "c2"  # falls back to id when name is None


# ── 4. apply_coupon_to_subscription ──────────────────────────────────────────

def test_apply_coupon_no_stripe():
    from app.core.coupon_service import apply_coupon_to_subscription
    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""}, clear=False):
        result = apply_coupon_to_subscription("org-123", "CODE")
    assert result["success"] is False
    assert "not configured" in result["message"].lower()


def test_apply_coupon_empty_code():
    from app.core.coupon_service import apply_coupon_to_subscription
    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}, clear=False):
        result = apply_coupon_to_subscription("org-123", "")
    assert result["success"] is False
    assert "required" in result["message"].lower()


def test_apply_coupon_no_customer():
    from app.core.coupon_service import apply_coupon_to_subscription

    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data={"stripe_customer_id": None})

    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}, clear=False):
        with patch("app.core.database.get_supabase_admin", return_value=mock_sb):
            with patch("app.core.coupon_service._init_stripe", return_value=MagicMock()):
                result = apply_coupon_to_subscription("org-123", "CODE")
    assert result["success"] is False
    assert "billing account" in result["message"].lower()


# ── 5. get_org_discount ──────────────────────────────────────────────────────

def test_get_org_discount_no_stripe():
    from app.core.coupon_service import get_org_discount
    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""}, clear=False):
        result = get_org_discount("org-123")
    assert result is None


# ── 6. Billing endpoint existence ────────────────────────────────────────────

def test_billing_has_validate_coupon_endpoint():
    src = open(os.path.join(ROOT, "app", "api", "endpoints", "billing.py")).read()
    assert "validate-coupon" in src
    assert "ValidateCouponRequest" in src


def test_billing_has_apply_coupon_endpoint():
    src = open(os.path.join(ROOT, "app", "api", "endpoints", "billing.py")).read()
    assert "apply-coupon" in src
    assert "ApplyCouponRequest" in src


def test_billing_has_discount_endpoint():
    src = open(os.path.join(ROOT, "app", "api", "endpoints", "billing.py")).read()
    assert '"/discount"' in src or "discount" in src


# ── 7. Frontend API methods ──────────────────────────────────────────────────

def test_frontend_api_has_validate_coupon():
    src = open(os.path.join(FRONTEND, "lib", "api.ts")).read()
    assert "validateCoupon" in src
    assert "validate-coupon" in src


def test_frontend_api_has_apply_coupon():
    src = open(os.path.join(FRONTEND, "lib", "api.ts")).read()
    assert "applyCoupon" in src
    assert "apply-coupon" in src


def test_frontend_api_has_get_org_discount():
    src = open(os.path.join(FRONTEND, "lib", "api.ts")).read()
    assert "getOrgDiscount" in src
    assert "/billing/discount" in src


# ── 8. Frontend billing page coupon UI ───────────────────────────────────────

def test_billing_page_has_promo_code_section():
    src = open(os.path.join(FRONTEND, "app", "settings", "billing", "page.tsx")).read()
    assert "Promo Code" in src
    assert "couponCode" in src


def test_billing_page_has_apply_button():
    src = open(os.path.join(FRONTEND, "app", "settings", "billing", "page.tsx")).read()
    assert "handleApplyCoupon" in src
    assert "Apply" in src


def test_billing_page_has_discount_display():
    src = open(os.path.join(FRONTEND, "app", "settings", "billing", "page.tsx")).read()
    assert "Active discount" in src
    assert "discount" in src


def test_billing_page_has_coupon_result_feedback():
    src = open(os.path.join(FRONTEND, "app", "settings", "billing", "page.tsx")).read()
    assert "couponResult" in src
    assert "success" in src


def test_billing_page_imports_tag_icon():
    src = open(os.path.join(FRONTEND, "app", "settings", "billing", "page.tsx")).read()
    assert "Tag" in src


# ── 9. coupon_service function signatures ────────────────────────────────────

def test_validate_coupon_returns_none_for_none_input():
    from app.core.coupon_service import validate_coupon
    assert validate_coupon(None) is None


def test_apply_coupon_returns_dict():
    from app.core.coupon_service import apply_coupon_to_subscription
    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""}, clear=False):
        result = apply_coupon_to_subscription("org-1", "CODE")
    assert isinstance(result, dict)
    assert "success" in result
    assert "message" in result


def test_get_org_discount_returns_none_or_dict():
    from app.core.coupon_service import get_org_discount
    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""}, clear=False):
        result = get_org_discount("org-1")
    assert result is None
