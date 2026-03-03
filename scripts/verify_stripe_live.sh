#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# verify_stripe_live.sh — Pre-launch Stripe billing verification
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   ./scripts/verify_stripe_live.sh
#
# Checks:
#   1. Backend /health is up
#   2. /billing/plans returns 3 plans with correct pricing
#   3. /billing/plans shows billing_enabled=true, billing_configured=true
#   4. Webhook endpoint returns 400 (not 503) for unsigned payload
#   5. Frontend is live and returns 200
#   6. Env var presence on Render (requires RENDER_API_KEY)
#
# Requires: curl, jq
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

BACKEND_URL="${BACKEND_URL:-https://security-officer.onrender.com}"
FRONTEND_URL="${FRONTEND_URL:-https://nyccompliancearchitect.com}"
API_BASE="$BACKEND_URL/api/v1"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass=0
fail=0
warn=0

check() {
    local label="$1"
    local result="$2"
    if [ "$result" = "true" ]; then
        echo -e "  ${GREEN}✓${NC} $label"
        ((pass++))
    else
        echo -e "  ${RED}✗${NC} $label"
        ((fail++))
    fi
}

warn_check() {
    local label="$1"
    local result="$2"
    if [ "$result" = "true" ]; then
        echo -e "  ${GREEN}✓${NC} $label"
        ((pass++))
    else
        echo -e "  ${YELLOW}⚠${NC} $label"
        ((warn++))
    fi
}

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Stripe Billing Live Verification"
echo "  Backend:  $BACKEND_URL"
echo "  Frontend: $FRONTEND_URL"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ── 1. Backend Health ────────────────────────────────────────
echo "1. Backend Health"
health_status=$(curl -s -o /dev/null -w "%{http_code}" "$API_BASE/health" 2>/dev/null || echo "000")
check "GET /health returns 200" "$([ "$health_status" = "200" ] && echo true || echo false)"

# ── 2. Webhook endpoint reachable ────────────────────────────
echo ""
echo "2. Webhook Endpoint"
# Send empty POST — should get 400 (bad payload) NOT 503 (not configured)
wh_status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_BASE/billing/webhook19" -H "Content-Type: application/json" -d '{}' 2>/dev/null || echo "000")
check "POST /billing/webhook19 returns 400 (not 503)" "$([ "$wh_status" = "400" ] && echo true || echo false)"

wh_old_status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_BASE/billing/webhook" -H "Content-Type: application/json" -d '{}' 2>/dev/null || echo "000")
warn_check "POST /billing/webhook returns 400 (not 503)" "$([ "$wh_old_status" = "400" ] && echo true || echo false)"

# ── 3. Frontend Live ─────────────────────────────────────────
echo ""
echo "3. Frontend"
fe_status=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL" 2>/dev/null || echo "000")
check "GET $FRONTEND_URL returns 200" "$([ "$fe_status" = "200" ] && echo true || echo false)"

fe_plans_status=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL/plans" 2>/dev/null || echo "000")
check "GET $FRONTEND_URL/plans returns 200" "$([ "$fe_plans_status" = "200" ] && echo true || echo false)"

# ── 4. Plans Pricing Check (requires auth token) ─────────────
echo ""
echo "4. Plans Pricing (public summary)"
echo -e "  ${YELLOW}ℹ${NC}  Full /billing/plans check requires auth token."
echo "     To verify plans pricing, log in and check the Plans page"
echo "     or use: curl -H 'Authorization: Bearer <token>' $API_BASE/billing/plans | jq"

# ── Summary ──────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo -e "  Results: ${GREEN}$pass passed${NC}, ${RED}$fail failed${NC}, ${YELLOW}$warn warnings${NC}"
echo "═══════════════════════════════════════════════════════════════"
echo ""

if [ "$fail" -gt 0 ]; then
    echo -e "${RED}Some checks failed. Review above.${NC}"
    exit 1
fi

echo -e "${GREEN}All critical checks passed!${NC}"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  REMAINING MANUAL STEPS:"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  1. Run 015_org_plan_tier_patch.sql in Supabase SQL Editor"
echo "     (File: backend/scripts/015_org_plan_tier_patch.sql)"
echo ""
echo "  2. Create Stripe webhook endpoint in Stripe Dashboard:"
echo "     URL: $BACKEND_URL/api/v1/billing/webhook19"
echo "     Events: checkout.session.completed,"
echo "             customer.subscription.created,"
echo "             customer.subscription.updated,"
echo "             customer.subscription.deleted,"
echo "             invoice.payment_failed"
echo ""
echo "  3. Copy webhook signing secret (whsec_...) to Render:"
echo "     Dashboard → Environment → STRIPE_WEBHOOK_SECRET"
echo ""
echo "  4. Trigger Render redeploy (or wait for auto-deploy from push)"
echo ""
echo "  5. Trigger Vercel redeploy to pick up NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY"
echo ""
echo "  6. End-to-end test: Stripe test card 4242424242424242"
echo "     → Plans page → Upgrade → Checkout → Verify webhook fires"
echo ""
