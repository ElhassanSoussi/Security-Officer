#!/usr/bin/env bash
# ──────────────────────────────────────────────────
# Stripe Billing Smoke Test
# ──────────────────────────────────────────────────
set -euo pipefail

BASE="${API_BASE:-http://localhost:8000}"
PASS=0
FAIL=0

bold() { printf "\n\033[1m%s\033[0m\n" "$1"; }
check() {
    local desc=$1 expected=$2 actual=$3
    if [[ "$actual" == "$expected" ]]; then
        printf "  ✅ %s (HTTP %s)\n" "$desc" "$actual"
        ((PASS++))
    else
        printf "  ❌ %s — expected %s, got %s\n" "$desc" "$expected" "$actual"
        ((FAIL++))
    fi
}

# ── Section 1: Checkout Session endpoint ──
bold "1. POST /billing/create-checkout-session (no auth)"
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/billing/create-checkout-session" \
    -H "Content-Type: application/json" \
    -d '{"org_id":"test","plan_tier":"growth"}')
check "Should require auth" "403" "$CODE"

bold "2. POST /billing/create-checkout-session (bad plan)"
# Even with a fake JWT, should get 401/403 first
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/billing/create-checkout-session" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer fake-token" \
    -d '{"org_id":"00000000-0000-0000-0000-000000000000","plan_tier":"nonexistent"}')
# 401 or 403 expected
[[ "$CODE" =~ ^(401|403)$ ]] && check "Rejects bad token" "$CODE" "$CODE" || check "Rejects bad token" "401|403" "$CODE"

# ── Section 2: Webhook endpoint ──
bold "3. POST /billing/webhook (no signature)"
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/billing/webhook" \
    -H "Content-Type: application/json" \
    -d '{"type":"test"}')
check "Rejects unsigned webhook" "400" "$CODE"

bold "4. POST /billing/webhook (bad signature)"
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/billing/webhook" \
    -H "Content-Type: application/json" \
    -H "stripe-signature: t=123,v1=bad" \
    -d '{"type":"test"}')
check "Rejects bad signature" "400" "$CODE"

# ── Section 3: Plans endpoint ──
bold "5. GET /billing/plans (no auth)"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/billing/plans")
check "Plans requires auth" "403" "$CODE"

# ── Section 4: Subscription endpoint ──
bold "6. GET /billing/subscription (no auth)"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/billing/subscription")
check "Subscription requires auth" "403" "$CODE"

# ── Section 5: Summary endpoint ──
bold "7. GET /billing/summary (no auth)"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/billing/summary")
check "Summary requires auth" "403" "$CODE"

# ── Section 6: Portal endpoint ──
bold "8. POST /billing/portal (no auth)"
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/billing/portal")
check "Portal requires auth" "403" "$CODE"

# ── Results ──
bold "━━━ Results ━━━"
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
[[ $FAIL -gt 0 ]] && exit 1 || exit 0
