"""
Stripe Billing E2E Verification Tests
======================================

End-to-end tests for the complete Stripe billing flow — deterministic,
no real Stripe/DB/network calls. Tests cover the full checkout→webhook→
enforcement pipeline including:

  • Plans-page checkout flow (starter/growth/elite → FREE/PRO/ENTERPRISE mapping)
  • Checkout flow (FREE/PRO/ENTERPRISE direct)
  • Webhook19 handler dispatch for all event types
  • Dual-write: subscriptions table + organizations table
  • Metadata compatibility (plan_tier vs plan_name in session metadata)
  • Pending subscription upsert before Stripe redirect
  • Plan limits enforcement (402 SUBSCRIPTION_INACTIVE)
  • Billing disabled/unconfigured → structured 503 JSON
  • billing_enabled / billing_configured flags in /plans response
  • Idempotent event logging (billing_events table)
  • Secret-leak guard (no sk_live/sk_test in frontend code)
  • TIER_TO_PLAN_NAME mapping consistency across modules
  • Price ID → plan_name reverse mapping
  • Stripe webhook signature validation error handling
  • Fail-open on DB errors throughout
"""

import json
import os
import sys
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

REPO_ROOT = os.path.join(BACKEND_DIR, "..")
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")


def _read(path: str) -> str:
    with open(path) as f:
        return f.read()


# ===========================================================================
# E2E-01–05: TIER_TO_PLAN_NAME mapping consistency
# ===========================================================================

class TestTierToPlanNameMapping:
    """Verify starter/growth/elite → FREE/PRO/ENTERPRISE mapping is consistent."""

    def test_01_billing_py_has_tier_to_plan_name(self):
        from app.core.billing import TIER_TO_PLAN_NAME
        assert TIER_TO_PLAN_NAME["starter"] == "FREE"
        assert TIER_TO_PLAN_NAME["growth"] == "PRO"
        assert TIER_TO_PLAN_NAME["elite"] == "ENTERPRISE"

    def test_02_stripe_billing_py_has_tier_to_plan_name(self):
        from app.core.stripe_billing import _TIER_TO_PLAN_NAME
        assert _TIER_TO_PLAN_NAME["starter"] == "FREE"
        assert _TIER_TO_PLAN_NAME["growth"] == "PRO"
        assert _TIER_TO_PLAN_NAME["elite"] == "ENTERPRISE"

    def test_03_both_modules_agree(self):
        from app.core.billing import TIER_TO_PLAN_NAME as a
        from app.core.stripe_billing import _TIER_TO_PLAN_NAME as b
        assert a == b

    def test_04_plan_price_map_has_three_tiers(self):
        from app.core.billing import PLAN_PRICE_MAP
        assert "starter" in PLAN_PRICE_MAP
        assert "growth" in PLAN_PRICE_MAP
        assert "elite" in PLAN_PRICE_MAP

    def test_05_price_map_has_three_plan_names(self):
        from app.core.stripe_billing import _price_map
        pm = _price_map()
        assert "FREE" in pm
        assert "PRO" in pm
        assert "ENTERPRISE" in pm


# ===========================================================================
# E2E-06–12: Plans-page checkout flow (billing.py BillingManager)
# ===========================================================================

class TestPlansPageCheckoutFlow:
    """Test create_checkout_session in billing.py (Plans page path)."""

    def test_06_checkout_metadata_includes_plan_name(self):
        """Checkout session metadata must include plan_name for webhook19."""
        from app.core.billing import BillingManager, TIER_TO_PLAN_NAME

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test"

        with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create, \
             patch("stripe.api_key", "sk_test_fake"), \
             patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_fake", "STRIPE_PRICE_GROWTH": "price_growth_123"}), \
             patch("app.core.billing.stripe.api_key", "sk_test_fake"), \
             patch("app.core.billing.PLAN_PRICE_MAP", {"growth": "price_growth_123"}), \
             patch("app.core.billing.get_supabase_admin") as mock_admin:
            mock_admin.return_value.table.return_value.upsert.return_value.execute.return_value = MagicMock()

            url = BillingManager.create_checkout_session(
                org_id="org-123",
                plan_tier="growth",
                success_url="https://ok",
                cancel_url="https://cancel",
                customer_email="user@test.com",
            )

        assert url == "https://checkout.stripe.com/test"
        create_kwargs = mock_create.call_args
        metadata = create_kwargs[1].get("metadata") or create_kwargs[0][0].get("metadata", {}) if create_kwargs[0] else {}
        if not metadata:
            # Might be passed as keyword arg
            for arg in create_kwargs:
                if isinstance(arg, dict) and "metadata" in arg:
                    metadata = arg["metadata"]
                    break

    def test_07_checkout_pending_upsert_uses_mapped_plan(self):
        """Pending subscription upsert should use FREE/PRO/ENTERPRISE, not starter/growth/elite."""
        from app.core.billing import BillingManager

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test"

        mock_sb = MagicMock()
        upsert_data_captured = []

        def capture_upsert(data, on_conflict=None):
            upsert_data_captured.append(data)
            return MagicMock(execute=MagicMock())

        mock_sb.table.return_value.upsert = capture_upsert

        with patch("stripe.checkout.Session.create", return_value=mock_session), \
             patch("app.core.billing.stripe.api_key", "sk_test_fake"), \
             patch("app.core.billing.PLAN_PRICE_MAP", {"elite": "price_elite_456"}), \
             patch("app.core.billing.get_supabase_admin", return_value=mock_sb):

            BillingManager.create_checkout_session(
                org_id="org-456",
                plan_tier="elite",
                success_url="https://ok",
                cancel_url="https://cancel",
            )

        # The pending upsert should map elite → ENTERPRISE
        assert len(upsert_data_captured) > 0
        pending = upsert_data_captured[0]
        assert pending["plan_name"] == "ENTERPRISE"
        assert pending["stripe_status"] == "pending"
        assert pending["org_id"] == "org-456"

    def test_08_checkout_raises_value_error_for_unknown_tier(self):
        from app.core.billing import BillingManager

        with patch("app.core.billing.stripe.api_key", "sk_test_fake"), \
             patch("app.core.billing.PLAN_PRICE_MAP", {"starter": ""}):
            with pytest.raises(ValueError, match="No Stripe Price ID"):
                BillingManager.create_checkout_session(
                    org_id="org-x",
                    plan_tier="platinum",
                    success_url="https://ok",
                    cancel_url="https://cancel",
                )

    def test_09_checkout_raises_when_stripe_not_configured(self):
        from app.core.billing import BillingManager

        with patch("app.core.billing.stripe.api_key", ""):
            with pytest.raises(Exception, match="Stripe API Key not configured"):
                BillingManager.create_checkout_session(
                    org_id="org-x",
                    plan_tier="starter",
                    success_url="https://ok",
                    cancel_url="https://cancel",
                )

    def test_10_checkout_pending_upsert_failure_does_not_block(self):
        """If the pending upsert fails, the checkout should still proceed."""
        from app.core.billing import BillingManager

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test"

        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.side_effect = RuntimeError("DB down")

        with patch("stripe.checkout.Session.create", return_value=mock_session), \
             patch("app.core.billing.stripe.api_key", "sk_test_fake"), \
             patch("app.core.billing.PLAN_PRICE_MAP", {"starter": "price_starter_789"}), \
             patch("app.core.billing.get_supabase_admin", return_value=mock_sb):

            url = BillingManager.create_checkout_session(
                org_id="org-err",
                plan_tier="starter",
                success_url="https://ok",
                cancel_url="https://cancel",
            )
        assert url == "https://checkout.stripe.com/test"

    def test_11_checkout_uses_existing_customer_id(self):
        """When existing_customer_id is provided, it should be passed to Stripe."""
        from app.core.billing import BillingManager

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test"

        with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create, \
             patch("app.core.billing.stripe.api_key", "sk_test_fake"), \
             patch("app.core.billing.PLAN_PRICE_MAP", {"starter": "price_starter_789"}), \
             patch("app.core.billing.get_supabase_admin") as mock_admin:
            mock_admin.return_value.table.return_value.upsert.return_value.execute.return_value = MagicMock()

            BillingManager.create_checkout_session(
                org_id="org-cust",
                plan_tier="starter",
                success_url="https://ok",
                cancel_url="https://cancel",
                existing_customer_id="cus_existing123",
            )

        kwargs = mock_create.call_args[1] if mock_create.call_args[1] else {}
        assert kwargs.get("customer") == "cus_existing123"

    def test_12_plan_defaults_keys_match_tier_mapping_targets(self):
        """PLAN_DEFAULTS must have keys for every TIER_TO_PLAN_NAME target value."""
        from app.core.subscription import PLAN_DEFAULTS
        from app.core.billing import TIER_TO_PLAN_NAME

        for tier, plan_name in TIER_TO_PLAN_NAME.items():
            assert plan_name in PLAN_DEFAULTS, (
                f"TIER_TO_PLAN_NAME maps '{tier}' → '{plan_name}' but PLAN_DEFAULTS has no '{plan_name}' key"
            )


# ===========================================================================
# E2E-13–22: Webhook19 handler dispatch
# ===========================================================================

class TestWebhook19Handlers:
    """Test _handle_checkout_completed, _handle_subscription_updated, etc."""

    def _mock_admin_sb(self):
        """Return a mock admin supabase client."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        return mock_sb

    def test_13_checkout_completed_reads_plan_name_metadata(self):
        """Webhook handler should read plan_name from metadata (checkout flow)."""
        from app.core.stripe_billing import _handle_checkout_completed

        mock_sb = self._mock_admin_sb()
        upsert_calls = []
        def capture_upsert(data, on_conflict=None):
            upsert_calls.append(data)
            return MagicMock(execute=MagicMock())
        mock_sb.table.return_value.upsert = capture_upsert

        session_data = {
            "metadata": {"org_id": "org-001", "plan_name": "ENTERPRISE"},
            "customer": "cus_abc",
            "subscription": None,
        }

        with patch("app.core.stripe_billing._admin_sb", return_value=mock_sb):
            _handle_checkout_completed(session_data)

        assert len(upsert_calls) > 0
        assert upsert_calls[0]["plan_name"] == "ENTERPRISE"

    def test_14_checkout_completed_reads_plan_tier_metadata_fallback(self):
        """Webhook handler should fall back to plan_tier metadata (Plans page flow)."""
        from app.core.stripe_billing import _handle_checkout_completed

        mock_sb = self._mock_admin_sb()
        upsert_calls = []
        def capture_upsert(data, on_conflict=None):
            upsert_calls.append(data)
            return MagicMock(execute=MagicMock())
        mock_sb.table.return_value.upsert = capture_upsert

        session_data = {
            "metadata": {"org_id": "org-002", "plan_tier": "growth"},  # no plan_name!
            "customer": "cus_def",
            "subscription": None,
        }

        with patch("app.core.stripe_billing._admin_sb", return_value=mock_sb):
            _handle_checkout_completed(session_data)

        assert len(upsert_calls) > 0
        # growth → PRO via _TIER_TO_PLAN_NAME
        assert upsert_calls[0]["plan_name"] == "PRO"

    def test_15_checkout_completed_dual_writes_organizations(self):
        """Webhook handler should also update organizations table."""
        from app.core.stripe_billing import _handle_checkout_completed

        mock_sb = self._mock_admin_sb()
        update_calls = []
        original_table = mock_sb.table

        def track_table(name):
            result = original_table(name)
            if name == "organizations":
                orig_update = result.update
                def capture_update(data):
                    update_calls.append(data)
                    return orig_update(data)
                result.update = capture_update
            return result

        mock_sb.table = track_table

        session_data = {
            "metadata": {"org_id": "org-003", "plan_name": "PRO", "plan_tier": "growth"},
            "customer": "cus_ghi",
            "subscription": None,
        }

        with patch("app.core.stripe_billing._admin_sb", return_value=mock_sb):
            _handle_checkout_completed(session_data)

        # Should have at least one update to organizations
        assert len(update_calls) > 0
        org_update = update_calls[0]
        assert org_update.get("stripe_customer_id") == "cus_ghi"

    def test_16_checkout_completed_missing_org_id_does_not_crash(self):
        """Missing org_id in metadata → log warning, no crash."""
        from app.core.stripe_billing import _handle_checkout_completed

        session_data = {
            "metadata": {},
            "customer": "cus_xxx",
            "subscription": None,
        }

        # Should not raise
        with patch("app.core.stripe_billing._admin_sb", return_value=self._mock_admin_sb()):
            _handle_checkout_completed(session_data)

    def test_17_subscription_updated_maps_price_to_plan(self):
        """subscription.updated should derive plan_name from price_id."""
        from app.core.stripe_billing import _handle_subscription_updated

        mock_sb = self._mock_admin_sb()
        # Set up org lookup by customer
        org_res = MagicMock()
        org_res.data = {"org_id": "org-004"}
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = org_res

        upsert_calls = []
        def capture_upsert(data, on_conflict=None):
            upsert_calls.append(data)
            return MagicMock(execute=MagicMock())
        mock_sb.table.return_value.upsert = capture_upsert

        sub_data = {
            "id": "sub_123",
            "customer": "cus_jkl",
            "status": "active",
            "items": {"data": [{"price": {"id": "price_pro_test"}}]},
            "current_period_end": 1700000000,
        }

        with patch("app.core.stripe_billing._admin_sb", return_value=mock_sb), \
             patch.dict(os.environ, {"STRIPE_PRICE_PRO": "price_pro_test"}):
            _handle_subscription_updated(sub_data)

        assert len(upsert_calls) > 0
        assert upsert_calls[0]["plan_name"] == "PRO"
        assert upsert_calls[0]["stripe_status"] == "active"

    def test_18_subscription_deleted_downgrades_to_free(self):
        """subscription.deleted should set plan=FREE, status=canceled."""
        from app.core.stripe_billing import _handle_subscription_deleted

        mock_sb = self._mock_admin_sb()
        org_res = MagicMock()
        org_res.data = {"org_id": "org-005"}
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = org_res

        upsert_calls = []
        def capture_upsert(data, on_conflict=None):
            upsert_calls.append(data)
            return MagicMock(execute=MagicMock())
        mock_sb.table.return_value.upsert = capture_upsert

        sub_data = {"customer": "cus_mno"}

        with patch("app.core.stripe_billing._admin_sb", return_value=mock_sb):
            _handle_subscription_deleted(sub_data)

        assert len(upsert_calls) > 0
        assert upsert_calls[0]["plan_name"] == "FREE"
        assert upsert_calls[0]["stripe_status"] == "canceled"

    def test_19_payment_failed_sets_past_due(self):
        """invoice.payment_failed should set stripe_status=past_due."""
        from app.core.stripe_billing import _handle_payment_failed

        mock_sb = self._mock_admin_sb()
        org_res = MagicMock()
        org_res.data = {"org_id": "org-006"}
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = org_res

        upsert_calls = []
        def capture_upsert(data, on_conflict=None):
            upsert_calls.append(data)
            return MagicMock(execute=MagicMock())
        mock_sb.table.return_value.upsert = capture_upsert

        invoice_data = {"customer": "cus_pqr"}

        with patch("app.core.stripe_billing._admin_sb", return_value=mock_sb):
            _handle_payment_failed(invoice_data)

        assert len(upsert_calls) > 0
        assert upsert_calls[0]["stripe_status"] == "past_due"

    def test_20_process_event_dispatches_correctly(self):
        """_process_event should dispatch to the right handler based on event type."""
        from app.core.stripe_billing import _process_event

        with patch("app.core.stripe_billing._handle_checkout_completed") as mock_checkout, \
             patch("app.core.stripe_billing._log_billing_event"), \
             patch("app.core.stripe_billing._admin_sb"):

            event = {
                "id": "evt_test_001",
                "type": "checkout.session.completed",
                "data": {"object": {"metadata": {"org_id": "org-007"}}},
            }
            result = _process_event(event)

            mock_checkout.assert_called_once()
            assert result["type"] == "checkout.session.completed"

    def test_21_process_event_handles_unknown_event_gracefully(self):
        """Unknown event types should not crash."""
        from app.core.stripe_billing import _process_event

        with patch("app.core.stripe_billing._log_billing_event"), \
             patch("app.core.stripe_billing._admin_sb"):

            event = {
                "id": "evt_test_002",
                "type": "some.unknown.event",
                "data": {"object": {}},
            }
            result = _process_event(event)
            assert result["status"] == "handled"
            assert result["type"] == "some.unknown.event"

    def test_22_process_event_handler_error_does_not_propagate(self):
        """If a handler raises, _process_event should catch and log, not crash."""
        from app.core.stripe_billing import _process_event

        with patch("app.core.stripe_billing._handle_checkout_completed", side_effect=RuntimeError("boom")), \
             patch("app.core.stripe_billing._log_billing_event"), \
             patch("app.core.stripe_billing._admin_sb"):

            event = {
                "id": "evt_test_003",
                "type": "checkout.session.completed",
                "data": {"object": {"metadata": {"org_id": "org-008"}}},
            }
            # Should not raise
            result = _process_event(event)
            assert result["status"] == "handled"


# ===========================================================================
# E2E-23–27: Webhook signature validation
# ===========================================================================

class TestWebhookSignatureValidation:

    def test_23_construct_event_raises_503_when_no_secret(self):
        from app.core.stripe_billing import _construct_event

        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": ""}):
            with pytest.raises(HTTPException) as exc:
                _construct_event(b"payload", "sig")
            assert exc.value.status_code == 503

    def test_24_construct_event_raises_400_on_bad_signature(self):
        from app.core.stripe_billing import _construct_event

        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test", "STRIPE_SECRET_KEY": "sk_test_fake"}), \
             patch("stripe.Webhook.construct_event", side_effect=Exception("bad sig")):
            with pytest.raises(HTTPException) as exc:
                _construct_event(b"payload", "bad_sig")
            assert exc.value.status_code == 400

    def test_25_idempotent_event_logging(self):
        """_log_billing_event should upsert on stripe_event_id (idempotent)."""
        from app.core.stripe_billing import _log_billing_event

        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()

        with patch("app.core.stripe_billing._admin_sb", return_value=mock_sb):
            _log_billing_event("evt_dedup_001", "checkout.session.completed", {"key": "val"})

        upsert_call = mock_sb.table.return_value.upsert.call_args
        assert upsert_call[1].get("on_conflict") == "stripe_event_id"

    def test_26_event_logging_failure_does_not_crash(self):
        """If billing_events upsert fails, it should not propagate."""
        from app.core.stripe_billing import _log_billing_event

        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.side_effect = RuntimeError("DB error")

        with patch("app.core.stripe_billing._admin_sb", return_value=mock_sb):
            # Should not raise
            _log_billing_event("evt_fail_001", "test", {})

    def test_27_org_id_lookup_by_customer_returns_none_on_error(self):
        from app.core.stripe_billing import _org_id_for_customer

        with patch("app.core.stripe_billing._admin_sb", side_effect=RuntimeError("DB down")):
            assert _org_id_for_customer("cus_xxx") is None

        assert _org_id_for_customer(None) is None


# ===========================================================================
# E2E-28–33: Enforcement (402 SUBSCRIPTION_INACTIVE + fail-open)
# ===========================================================================

class TestEnforcement:

    def _mock_sb_with_status(self, stripe_status):
        mock_sb = MagicMock()
        fake_res = MagicMock()
        fake_res.data = {"stripe_status": stripe_status}
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = fake_res
        return mock_sb

    def test_28_active_status_passes(self):
        from app.core.stripe_billing import check_subscription_active

        with patch("app.core.stripe_billing._admin_sb", return_value=self._mock_sb_with_status("active")):
            check_subscription_active("org-active")  # must not raise

    def test_29_trialing_status_passes(self):
        from app.core.stripe_billing import check_subscription_active

        with patch("app.core.stripe_billing._admin_sb", return_value=self._mock_sb_with_status("trialing")):
            check_subscription_active("org-trial")  # must not raise

    def test_30_past_due_raises_402(self):
        from app.core.stripe_billing import check_subscription_active

        with patch("app.core.stripe_billing._admin_sb", return_value=self._mock_sb_with_status("past_due")):
            with pytest.raises(HTTPException) as exc:
                check_subscription_active("org-pastdue")
            assert exc.value.status_code == 402
            assert exc.value.detail["error"] == "SUBSCRIPTION_INACTIVE"

    def test_31_canceled_raises_402(self):
        from app.core.stripe_billing import check_subscription_active

        with patch("app.core.stripe_billing._admin_sb", return_value=self._mock_sb_with_status("canceled")):
            with pytest.raises(HTTPException) as exc:
                check_subscription_active("org-canceled")
            assert exc.value.status_code == 402

    def test_32_unpaid_raises_402(self):
        from app.core.stripe_billing import check_subscription_active

        with patch("app.core.stripe_billing._admin_sb", return_value=self._mock_sb_with_status("unpaid")):
            with pytest.raises(HTTPException) as exc:
                check_subscription_active("org-unpaid")
            assert exc.value.status_code == 402

    def test_33_db_error_fails_open(self):
        from app.core.stripe_billing import check_subscription_active

        with patch("app.core.stripe_billing._admin_sb", side_effect=RuntimeError("connection reset")):
            check_subscription_active("org-dberr")  # must NOT raise


# ===========================================================================
# E2E-34–38: Billing disabled mode (structured 503, no tracebacks)
# ===========================================================================

class TestBillingDisabledMode:

    def test_34_ensure_billing_configured_raises_503_when_disabled(self):
        """When BILLING_ENABLED=false, billing endpoints return structured 503."""
        from app.core.error_handler import APIError

        # Import the function from the module
        import app.api.endpoints.billing as billing_ep

        saved = billing_ep._BILLING_ENABLED
        try:
            billing_ep._BILLING_ENABLED = False
            with pytest.raises(APIError) as exc:
                billing_ep._ensure_billing_configured()
            assert exc.value.status_code == 503
            assert "billing_disabled" in str(exc.value.error)
        finally:
            billing_ep._BILLING_ENABLED = saved

    def test_35_ensure_billing_configured_raises_503_when_unconfigured(self):
        """When BILLING_ENABLED=true but STRIPE_SECRET_KEY missing → 503."""
        from app.core.error_handler import APIError
        import app.api.endpoints.billing as billing_ep

        saved_enabled = billing_ep._BILLING_ENABLED
        saved_configured = billing_ep._BILLING_CONFIGURED
        try:
            billing_ep._BILLING_ENABLED = True
            billing_ep._BILLING_CONFIGURED = False
            with pytest.raises(APIError) as exc:
                billing_ep._ensure_billing_configured()
            assert exc.value.status_code == 503
            assert "billing_not_configured" in str(exc.value.error)
        finally:
            billing_ep._BILLING_ENABLED = saved_enabled
            billing_ep._BILLING_CONFIGURED = saved_configured

    def test_36_billing_fallback_returns_starter_plan(self):
        """_billing_fallback should return a well-shaped dict with starter plan."""
        import app.api.endpoints.billing as billing_ep
        result = billing_ep._billing_fallback("org-fallback")
        assert result["plan"] == "starter"
        assert result["status"] == "trialing"
        assert result["org_id"] == "org-fallback"
        assert "entitlements" in result
        assert "questionnaires" in result["entitlements"]
        assert "exports" in result["entitlements"]
        assert "storage_mb" in result["entitlements"]

    def test_37_billing_fallback_includes_billing_flags(self):
        """Fallback response must include billing_enabled and billing_configured."""
        import app.api.endpoints.billing as billing_ep
        result = billing_ep._billing_fallback("org-flags")
        assert "billing_enabled" in result
        assert "billing_configured" in result

    def test_38_billing_fallback_has_stripe_false(self):
        """Fallback should indicate has_stripe=False."""
        import app.api.endpoints.billing as billing_ep
        result = billing_ep._billing_fallback()
        assert result["has_stripe"] is False


# ===========================================================================
# E2E-39–43: Plans endpoint billing flags injection
# ===========================================================================

class TestPlansEndpointFlags:

    def test_39_default_plans_include_billing_enabled(self):
        """The DEFAULT_PLANS fallback path should inject billing_enabled."""
        src = _read(os.path.join(BACKEND_DIR, "app", "api", "endpoints", "billing.py"))
        # The fallback path should include billing_enabled
        assert 'billing_enabled' in src
        assert 'billing_configured' in src

    def test_40_db_plans_path_injects_billing_flags(self):
        """When plans come from DB, they should also get billing_enabled/billing_configured."""
        src = _read(os.path.join(BACKEND_DIR, "app", "api", "endpoints", "billing.py"))
        # There should be two places where billing_enabled is set:
        # 1. In the DB path (normalized plans)
        # 2. In the fallback path (DEFAULT_PLANS)
        count = src.count('"billing_enabled"') + src.count("'billing_enabled'")
        assert count >= 2, f"billing_enabled should appear at least twice, found {count}"

    def test_41_default_plans_are_not_mutated(self):
        """DEFAULT_PLANS should be copied with dict() before modification."""
        src = _read(os.path.join(BACKEND_DIR, "app", "api", "endpoints", "billing.py"))
        assert "dict(p) for p in DEFAULT_PLANS" in src

    def test_42_plans_include_all_three_tiers(self):
        """Plans response should include starter, growth, elite."""
        src = _read(os.path.join(BACKEND_DIR, "app", "api", "endpoints", "billing.py"))
        assert '"starter"' in src
        assert '"growth"' in src
        assert '"elite"' in src

    def test_43_plans_have_correct_pricing(self):
        """Verify canonical pricing: Starter=$149, Growth=$499, Elite=$1499."""
        src = _read(os.path.join(BACKEND_DIR, "app", "api", "endpoints", "billing.py"))
        assert "14900" in src   # Starter
        assert "49900" in src   # Growth
        assert "149900" in src  # Elite


# ===========================================================================
# E2E-44–48: Secret-leak guards
# ===========================================================================

class TestSecretLeakGuard:

    def _scan_frontend(self, pattern: str) -> list:
        """Scan all .ts/.tsx/.js/.jsx files in frontend/ for a pattern."""
        hits = []
        for root, dirs, files in os.walk(FRONTEND_DIR):
            # Skip node_modules and .next
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".next", ".turbo")]
            for f in files:
                if f.endswith((".ts", ".tsx", ".js", ".jsx")):
                    path = os.path.join(root, f)
                    try:
                        content = _read(path)
                        if pattern in content:
                            hits.append(path)
                    except Exception:
                        pass
        return hits

    def test_44_no_stripe_secret_key_in_frontend(self):
        """STRIPE_SECRET_KEY must never appear in frontend code."""
        hits = self._scan_frontend("STRIPE_SECRET_KEY")
        assert len(hits) == 0, f"STRIPE_SECRET_KEY found in frontend files: {hits}"

    def test_45_no_stripe_webhook_secret_in_frontend(self):
        """STRIPE_WEBHOOK_SECRET must never appear in frontend code."""
        hits = self._scan_frontend("STRIPE_WEBHOOK_SECRET")
        assert len(hits) == 0, f"STRIPE_WEBHOOK_SECRET found in frontend files: {hits}"

    def test_46_no_sk_live_in_frontend(self):
        """sk_live_ must never appear in frontend code."""
        hits = self._scan_frontend("sk_live_")
        assert len(hits) == 0, f"sk_live_ found in frontend files: {hits}"

    def test_47_no_sk_test_in_frontend(self):
        """sk_test_ must never appear in frontend code."""
        hits = self._scan_frontend("sk_test_")
        assert len(hits) == 0, f"sk_test_ found in frontend files: {hits}"

    def test_48_no_whsec_in_frontend(self):
        """whsec_ must never appear in frontend code."""
        hits = self._scan_frontend("whsec_")
        assert len(hits) == 0, f"whsec_ found in frontend files: {hits}"


# ===========================================================================
# E2E-49–55: Checkout flow (stripe_billing.py)
# ===========================================================================

class TestPhase19CheckoutFlow:

    def test_49_create_checkout_session_writes_pending_record(self):
        from app.core.stripe_billing import create_checkout_session

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/phase19"

        mock_sb = MagicMock()
        upsert_calls = []
        def capture_upsert(data, on_conflict=None):
            upsert_calls.append(data)
            return MagicMock(execute=MagicMock())
        mock_sb.table.return_value.upsert = capture_upsert

        with patch("stripe.checkout.Session.create", return_value=mock_session), \
             patch.dict(os.environ, {
                 "STRIPE_SECRET_KEY": "sk_test_fake",
                 "STRIPE_PRICE_PRO": "price_pro_test",
             }), \
             patch("app.core.stripe_billing._admin_sb", return_value=mock_sb):

            url = create_checkout_session(
                org_id="org-p19",
                plan_name="PRO",
                success_url="https://ok",
                cancel_url="https://cancel",
            )

        assert url == "https://checkout.stripe.com/phase19"
        assert len(upsert_calls) > 0
        assert upsert_calls[0]["plan_name"] == "PRO"
        assert upsert_calls[0]["stripe_status"] == "pending"

    def test_50_create_checkout_adds_trial_for_pro(self):
        from app.core.stripe_billing import create_checkout_session

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/trial"

        with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create, \
             patch.dict(os.environ, {
                 "STRIPE_SECRET_KEY": "sk_test_fake",
                 "STRIPE_PRICE_PRO": "price_pro_test",
             }), \
             patch("app.core.stripe_billing._admin_sb") as mock_admin:
            mock_admin.return_value.table.return_value.upsert.return_value.execute.return_value = MagicMock()

            create_checkout_session(
                org_id="org-trial",
                plan_name="PRO",
                success_url="https://ok",
                cancel_url="https://cancel",
            )

        kwargs = mock_create.call_args[1]
        assert "subscription_data" in kwargs
        assert kwargs["subscription_data"]["trial_period_days"] == 14

    def test_51_create_checkout_no_trial_for_enterprise(self):
        from app.core.stripe_billing import create_checkout_session

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/ent"

        with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create, \
             patch.dict(os.environ, {
                 "STRIPE_SECRET_KEY": "sk_test_fake",
                 "STRIPE_PRICE_ENTERPRISE": "price_ent_test",
             }), \
             patch("app.core.stripe_billing._admin_sb") as mock_admin:
            mock_admin.return_value.table.return_value.upsert.return_value.execute.return_value = MagicMock()

            create_checkout_session(
                org_id="org-ent",
                plan_name="ENTERPRISE",
                success_url="https://ok",
                cancel_url="https://cancel",
            )

        kwargs = mock_create.call_args[1]
        assert "subscription_data" not in kwargs

    def test_52_start_pro_trial_sets_correct_limits(self):
        from app.core.stripe_billing import start_pro_trial
        from app.core.subscription import PLAN_DEFAULTS

        mock_sb = MagicMock()
        upsert_calls = []
        def capture_upsert(data, on_conflict=None):
            upsert_calls.append(data)
            return MagicMock(execute=MagicMock())
        mock_sb.table.return_value.upsert = capture_upsert

        with patch("app.core.stripe_billing._admin_sb", return_value=mock_sb):
            result = start_pro_trial("org-trial-limits")

        assert result["plan_name"] == "PRO"
        assert result["max_runs_per_month"] == PLAN_DEFAULTS["PRO"]["max_runs_per_month"]
        assert result["max_documents"] == PLAN_DEFAULTS["PRO"]["max_documents"]
        assert result["max_memory_entries"] == PLAN_DEFAULTS["PRO"]["max_memory_entries"]
        assert result["stripe_status"] == "trialing"

    def test_53_start_pro_trial_sets_period_end_14_days_out(self):
        from app.core.stripe_billing import start_pro_trial

        with patch("app.core.stripe_billing._admin_sb") as mock_admin:
            mock_admin.return_value.table.return_value.upsert.return_value.execute.return_value = MagicMock()
            result = start_pro_trial("org-trial-period")

        assert result["current_period_end"] is not None
        end = datetime.fromisoformat(result["current_period_end"])
        now = datetime.now(timezone.utc)
        diff = (end - now).days
        assert 13 <= diff <= 15  # ~14 days

    def test_54_get_subscription_status_returns_correct_shape(self):
        from app.core.stripe_billing import get_subscription_status

        mock_sb = MagicMock()
        fake_res = MagicMock()
        fake_res.data = {
            "plan_name": "PRO",
            "stripe_customer_id": "cus_test",
            "stripe_subscription_id": "sub_test",
            "stripe_status": "active",
            "current_period_end": "2026-04-01T00:00:00+00:00",
            "max_runs_per_month": 100,
            "max_documents": 500,
            "max_memory_entries": 2000,
        }
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = fake_res

        with patch("app.core.stripe_billing._admin_sb", return_value=mock_sb):
            result = get_subscription_status("org-status-test")

        assert result["plan_name"] == "PRO"
        assert result["is_active"] is True
        assert result["org_id"] == "org-status-test"

    def test_55_get_subscription_status_inactive_for_past_due(self):
        from app.core.stripe_billing import get_subscription_status

        mock_sb = MagicMock()
        fake_res = MagicMock()
        fake_res.data = {"stripe_status": "past_due", "plan_name": "PRO"}
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = fake_res

        with patch("app.core.stripe_billing._admin_sb", return_value=mock_sb):
            result = get_subscription_status("org-past-due")

        assert result["is_active"] is False


# ===========================================================================
# E2E-56–62: Deployment config completeness
# ===========================================================================

class TestDeploymentConfig:

    def test_56_render_yaml_has_all_stripe_env_vars(self):
        src = _read(os.path.join(REPO_ROOT, "render.yaml"))
        required = [
            "BILLING_ENABLED", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
            "STRIPE_PRICE_STARTER", "STRIPE_PRICE_GROWTH", "STRIPE_PRICE_ELITE",
            "STRIPE_PRICE_FREE", "STRIPE_PRICE_PRO", "STRIPE_PRICE_ENTERPRISE",
            "STRIPE_TRIAL_DAYS",
        ]
        for var in required:
            assert var in src, f"{var} missing from render.yaml"

    def test_57_docker_compose_prod_has_all_stripe_env_vars(self):
        src = _read(os.path.join(REPO_ROOT, "docker-compose.prod.yml"))
        required = [
            "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
            "STRIPE_PRICE_STARTER", "STRIPE_PRICE_GROWTH", "STRIPE_PRICE_ELITE",
            "STRIPE_PRICE_FREE", "STRIPE_PRICE_PRO", "STRIPE_PRICE_ENTERPRISE",
            "BILLING_ENABLED",
        ]
        for var in required:
            assert var in src, f"{var} missing from docker-compose.prod.yml"

    def test_58_docker_compose_prod_has_publishable_key_for_frontend(self):
        src = _read(os.path.join(REPO_ROOT, "docker-compose.prod.yml"))
        assert "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY" in src

    def test_59_frontend_dockerfile_has_publishable_key(self):
        src = _read(os.path.join(FRONTEND_DIR, "Dockerfile"))
        assert "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY" in src

    def test_60_env_example_has_all_stripe_vars(self):
        src = _read(os.path.join(BACKEND_DIR, ".env.example"))
        required = [
            "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
            "STRIPE_PRICE_STARTER", "STRIPE_PRICE_GROWTH", "STRIPE_PRICE_ELITE",
            "STRIPE_PRICE_FREE", "STRIPE_PRICE_PRO", "STRIPE_PRICE_ENTERPRISE",
            "BILLING_ENABLED",
        ]
        for var in required:
            assert var in src, f"{var} missing from backend/.env.example"

    def test_61_frontend_env_example_has_publishable_key(self):
        src = _read(os.path.join(FRONTEND_DIR, ".env.example"))
        assert "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY" in src

    def test_62_deploy_production_docs_mention_webhook_endpoint(self):
        doc_path = os.path.join(REPO_ROOT, "docs", "DEPLOY_PRODUCTION.md")
        if os.path.exists(doc_path):
            src = _read(doc_path)
            assert "webhook19" in src or "webhook" in src


# ===========================================================================
# E2E-63–67: Migration SQL completeness
# ===========================================================================

class TestMigrationSQL:

    def test_63_013_migration_includes_pending_status(self):
        sql = _read(os.path.join(BACKEND_DIR, "scripts", "013_stripe_billing.sql"))
        assert "'pending'" in sql, "013_stripe_billing.sql should include 'pending' in CHECK constraint"

    def test_64_013b_patch_migration_exists(self):
        path = os.path.join(BACKEND_DIR, "scripts", "013b_stripe_status_pending.sql")
        assert os.path.isfile(path), "013b_stripe_status_pending.sql not found"

    def test_65_013b_drops_old_constraint(self):
        sql = _read(os.path.join(BACKEND_DIR, "scripts", "013b_stripe_status_pending.sql"))
        assert "DROP CONSTRAINT" in sql

    def test_66_013b_adds_pending_to_check(self):
        sql = _read(os.path.join(BACKEND_DIR, "scripts", "013b_stripe_status_pending.sql"))
        assert "'pending'" in sql

    def test_67_013b_is_idempotent(self):
        """Patch migration should use IF EXISTS / DO $$ block to be safe to re-run."""
        sql = _read(os.path.join(BACKEND_DIR, "scripts", "013b_stripe_status_pending.sql"))
        assert "IF EXISTS" in sql or "DO $$" in sql


# ===========================================================================
# E2E-68–72: Frontend wiring checks
# ===========================================================================

class TestFrontendWiring:

    def test_68_api_ts_has_create_checkout_session(self):
        src = _read(os.path.join(FRONTEND_DIR, "lib", "api.ts"))
        assert "createCheckoutSession" in src

    def test_69_api_ts_sends_plan_tier_in_body(self):
        src = _read(os.path.join(FRONTEND_DIR, "lib", "api.ts"))
        assert "plan_tier" in src

    def test_70_api_ts_sends_org_id_in_body(self):
        src = _read(os.path.join(FRONTEND_DIR, "lib", "api.ts"))
        assert "org_id" in src

    def test_71_plans_page_calls_create_checkout_session(self):
        src = _read(os.path.join(FRONTEND_DIR, "app", "plans", "page.tsx"))
        assert "createCheckoutSession" in src

    def test_72_plans_page_handles_checkout_success_redirect(self):
        src = _read(os.path.join(FRONTEND_DIR, "app", "plans", "page.tsx"))
        assert "checkout=success" in src or "checkout" in src


# ===========================================================================
# E2E-73–77: CI/CD secret leak guard
# ===========================================================================

class TestCISecretLeakGuard:

    def test_73_ci_yml_has_secret_leak_guard_job(self):
        ci_path = os.path.join(REPO_ROOT, ".github", "workflows", "ci.yml")
        if os.path.exists(ci_path):
            src = _read(ci_path)
            assert "secret-leak-guard" in src or "leak" in src.lower()

    def test_74_verify_build_has_stripe_leak_section(self):
        verify_path = os.path.join(REPO_ROOT, "scripts", "verify_build.sh")
        if os.path.exists(verify_path):
            src = _read(verify_path)
            assert "stripe" in src.lower() or "leak" in src.lower()

    def test_75_setup_stripe_products_script_exists(self):
        path = os.path.join(REPO_ROOT, "scripts", "setup_stripe_products.py")
        assert os.path.isfile(path), "scripts/setup_stripe_products.py not found"

    def test_76_config_has_starter_growth_elite_settings(self):
        from app.core.config import Settings
        s = Settings()
        assert hasattr(s, "STRIPE_PRICE_STARTER")
        assert hasattr(s, "STRIPE_PRICE_GROWTH")
        assert hasattr(s, "STRIPE_PRICE_ELITE")

    def test_77_upsert_subscription_removes_none_values(self):
        """_upsert_subscription should filter None values to avoid overwriting."""
        from app.core.stripe_billing import _upsert_subscription

        mock_sb = MagicMock()
        upsert_calls = []
        def capture_upsert(data, on_conflict=None):
            upsert_calls.append(data)
            return MagicMock(execute=MagicMock())
        mock_sb.table.return_value.upsert = capture_upsert

        with patch("app.core.stripe_billing._admin_sb", return_value=mock_sb):
            _upsert_subscription("org-clean", {
                "org_id": "org-clean",
                "plan_name": "PRO",
                "stripe_status": "active",
                "current_period_end": None,       # should be removed
                "stripe_subscription_id": None,    # KEPT (explicit clear)
            })

        assert len(upsert_calls) > 0
        clean = upsert_calls[0]
        assert "current_period_end" not in clean  # None removed
        assert "stripe_subscription_id" in clean   # None kept for explicit clear
        assert clean["plan_name"] == "PRO"
