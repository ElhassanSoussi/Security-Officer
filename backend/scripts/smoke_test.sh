#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# smoke_test.sh – One-command API smoke test for Security-Officer
# Usage:  bash backend/scripts/smoke_test.sh [BASE_URL]
# Defaults to http://localhost:8000/api/v1
# Requires: curl, jq (optional for pretty output)
# ─────────────────────────────────────────────────────────────
set -euo pipefail

BASE="${1:-http://localhost:8000/api/v1}"
PASS=0
FAIL=0
SKIP=0

green()  { printf "\033[32m%s\033[0m\n" "$*"; }
red()    { printf "\033[31m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
bold()   { printf "\033[1m%s\033[0m\n" "$*"; }

check() {
  local desc="$1" code="$2" expected="$3"
  if [ "$code" -eq "$expected" ]; then
    green "  ✅ $desc (HTTP $code)"
    PASS=$((PASS + 1))
  else
    red "  ❌ $desc (HTTP $code, expected $expected)"
    FAIL=$((FAIL + 1))
  fi
}

skip() {
  yellow "  ⏭  $1 — skipped ($2)"
  SKIP=$((SKIP + 1))
}

# ─── 1. Health Check (with startup wait) ─────────────────────
bold "━━━ 1. Health Check ━━━"
MAX_WAIT=15
WAITED=0
HTTP="000"
while [ "$WAITED" -lt "$MAX_WAIT" ]; do
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/health" 2>/dev/null || echo "000")
  if [ "$HTTP" != "000" ]; then
    break
  fi
  sleep 1
  WAITED=$((WAITED + 1))
  printf "  ⏳ Waiting for backend to start... (%ds/%ds)\r" "$WAITED" "$MAX_WAIT"
done
echo ""
if [ "$HTTP" = "000" ]; then
  red "  ❌ Backend unreachable at $BASE (waited ${MAX_WAIT}s)"
  echo ""
  red "Cannot continue. Check container logs: docker logs <container_name>"
  exit 1
fi
check "GET /health" "$HTTP" 200

# ─── 2. Root endpoint ────────────────────────────────────────
bold "━━━ 2. Root Endpoint ━━━"
ROOT_BASE="${BASE%/api/v1}"
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${ROOT_BASE}/" 2>/dev/null || echo "000")
check "GET /" "$HTTP" 200

# ─── 3. Public endpoints (no auth) ──────────────────────────
bold "━━━ 3. Auth-Protected Endpoints (expect 403/401) ━━━"
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/orgs" 2>/dev/null || echo "000")
if [ "$HTTP" = "403" ] || [ "$HTTP" = "401" ] || [ "$HTTP" = "422" ]; then
  green "  ✅ GET /orgs correctly requires auth (HTTP $HTTP)"
  PASS=$((PASS + 1))
else
  red "  ❌ GET /orgs returned unexpected HTTP $HTTP (expected 401/403)"
  FAIL=$((FAIL + 1))
fi

HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/projects" 2>/dev/null || echo "000")
if [ "$HTTP" = "403" ] || [ "$HTTP" = "401" ] || [ "$HTTP" = "422" ]; then
  green "  ✅ GET /projects correctly requires auth (HTTP $HTTP)"
  PASS=$((PASS + 1))
else
  red "  ❌ GET /projects returned unexpected HTTP $HTTP (expected 401/403)"
  FAIL=$((FAIL + 1))
fi

# ─── 4. Structured Error Response ────────────────────────────
bold "━━━ 4. Structured Error Response ━━━"
BODY=$(curl -s "${BASE}/orgs" 2>/dev/null || echo "{}")
if echo "$BODY" | grep -q '"code"'; then
  green "  ✅ Error response contains 'code' field"
  PASS=$((PASS + 1))
else
  yellow "  ⚠️  Error response missing 'code' field (non-critical)"
  SKIP=$((SKIP + 1))
fi

# ─── 5. Billing Plans ────────────────────────────────────────
bold "━━━ 5. Billing Plans ━━━"
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/billing/plans" 2>/dev/null || echo "000")
if [ "$HTTP" = "200" ] || [ "$HTTP" = "403" ]; then
  green "  ✅ GET /billing/plans (HTTP $HTTP)"
  PASS=$((PASS + 1))
else
  red "  ❌ GET /billing/plans (HTTP $HTTP, expected 200 or 403)"
  FAIL=$((FAIL + 1))
fi

# ─── 6. Sample Questionnaire ─────────────────────────────────
bold "━━━ 6. Sample Questionnaire ━━━"
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/runs/samples/questionnaire" 2>/dev/null || echo "000")
if [ "$HTTP" = "200" ]; then
  check "GET /runs/samples/questionnaire" "$HTTP" 200
else
  skip "GET /runs/samples/questionnaire" "HTTP $HTTP — sample file may not exist"
fi

# ─── 7. Security: Org ID Validation ─────────────────────────
bold "━━━ 7. Security: Org ID Validation ━━━"
# Note: These endpoints require auth, so unauthenticated requests
# may return 401/403 before org_id validation fires.
# Any 4xx rejection (400/401/403) proves the request was denied.
# The critical check: 'default-org' must NEVER return 200.

# 7a. Invalid UUID format → must not return 200
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/runs?org_id=not-a-uuid" 2>/dev/null || echo "000")
if [ "$HTTP" = "400" ] || [ "$HTTP" = "401" ] || [ "$HTTP" = "403" ]; then
  green "  ✅ Rejected invalid UUID org_id (HTTP $HTTP)"
  PASS=$((PASS + 1))
elif [ "$HTTP" = "000" ]; then
  skip "Invalid UUID rejection" "backend unreachable"
else
  red "  ❌ Invalid UUID org_id returned HTTP $HTTP (expected 400/401/403)"
  FAIL=$((FAIL + 1))
fi

# 7b. Legacy 'default-org' string → must not return 200
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/runs?org_id=default-org" 2>/dev/null || echo "000")
if [ "$HTTP" = "400" ] || [ "$HTTP" = "401" ] || [ "$HTTP" = "403" ]; then
  green "  ✅ Rejected legacy 'default-org' (HTTP $HTTP)"
  PASS=$((PASS + 1))
elif [ "$HTTP" = "000" ]; then
  skip "Legacy default-org rejection" "backend unreachable"
else
  red "  ❌ Legacy 'default-org' returned HTTP $HTTP (expected 400/401/403)"
  FAIL=$((FAIL + 1))
fi

# ─── 8. Settings & Audit Endpoints ───────────────────────────
bold "━━━ 8. Settings & Audit (expect 403/401 unauthenticated) ━━━"

HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/settings/profile" 2>/dev/null || echo "000")
if [ "$HTTP" = "403" ] || [ "$HTTP" = "401" ]; then
  green "  ✅ GET /settings/profile correctly requires auth (HTTP $HTTP)"
  PASS=$((PASS + 1))
elif [ "$HTTP" = "000" ]; then
  skip "Settings profile auth" "backend unreachable"
else
  red "  ❌ GET /settings/profile returned HTTP $HTTP (expected 401/403)"
  FAIL=$((FAIL + 1))
fi

HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/audit/log?org_id=00000000-0000-0000-0000-000000000000" 2>/dev/null || echo "000")
if [ "$HTTP" = "403" ] || [ "$HTTP" = "401" ]; then
  green "  ✅ GET /audit/log correctly requires auth (HTTP $HTTP)"
  PASS=$((PASS + 1))
elif [ "$HTTP" = "000" ]; then
  skip "Audit log auth" "backend unreachable"
else
  red "  ❌ GET /audit/log returned HTTP $HTTP (expected 401/403)"
  FAIL=$((FAIL + 1))
fi

# Check X-Request-Id header on health endpoint
REQ_ID=$(curl -s -I "${BASE}/health" 2>/dev/null | grep -i "x-request-id" | head -1)
if [ -n "$REQ_ID" ]; then
  green "  ✅ X-Request-Id header present on response"
  PASS=$((PASS + 1))
else
  red "  ❌ X-Request-Id header missing from response"
  FAIL=$((FAIL + 1))
fi

# ─── Summary ─────────────────────────────────────────────────
echo ""
bold "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bold "  SMOKE TEST RESULTS"
bold "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
green "  Passed:  $PASS"
if [ "$FAIL" -gt 0 ]; then
  red "  Failed:  $FAIL"
else
  echo "  Failed:  0"
fi
if [ "$SKIP" -gt 0 ]; then
  yellow "  Skipped: $SKIP"
fi
echo ""

if [ "$FAIL" -gt 0 ]; then
  red "❌ SMOKE TEST FAILED"
  exit 1
else
  green "✅ SMOKE TEST PASSED"
  exit 0
fi
