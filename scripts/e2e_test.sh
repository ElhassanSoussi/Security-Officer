#!/bin/bash
# E2E Test Script for NYC Compliance Architect
# Author: Elhassan Soussi
# Tests: Auth → Org → Analyze Excel → Export Excel (against backend on port 8000)
set -euo pipefail

API="http://127.0.0.1:8000/api/v1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLE="${ROOT}/backend/samples/sample_questionnaire.xlsx"

# Load env files for secrets (never hardcoded)
source "${ROOT}/.smoke.env" 2>/dev/null || true
[ -f "${ROOT}/frontend/.env.local" ] && set -a && source "${ROOT}/frontend/.env.local" && set +a
SUPABASE_URL="${NEXT_PUBLIC_SUPABASE_URL:?Set NEXT_PUBLIC_SUPABASE_URL in frontend/.env.local or environment}"
SUPABASE_ANON_KEY="${NEXT_PUBLIC_SUPABASE_ANON_KEY:?Set NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env.local or environment}"

PASS=0
FAIL=0

ok() { PASS=$((PASS+1)); echo "  ✅ $1"; }
fail() { FAIL=$((FAIL+1)); echo "  ❌ $1"; }

echo "========================================"
echo "  NYC Compliance Architect — E2E Tests"
echo "  Author: Elhassan Soussi"
echo "========================================"
echo ""

# --- 0. Backend health ---
echo "🔹 Step 0: Backend Health"
HTTP=$(curl -s -o /tmp/e2e_health.json -w "%{http_code}" "$API/health" 2>/dev/null || echo "000")
if [ "$HTTP" = "200" ]; then ok "Backend healthy (HTTP $HTTP)"; else fail "Backend unreachable (HTTP $HTTP)"; exit 1; fi

# --- 1. Auth ---
echo "🔹 Step 1: Supabase Authentication"
source "${ROOT}/.smoke.env" 2>/dev/null || true
EMAIL="${SMOKE_EMAIL:?Set SMOKE_EMAIL in .smoke.env or environment}"
PASS_W="${SMOKE_PASSWORD:?Set SMOKE_PASSWORD in .smoke.env or environment}"

curl -sS "${SUPABASE_URL}/auth/v1/token?grant_type=password" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASS_W}\"}" \
  -o /tmp/e2e_auth.json 2>/dev/null

TOKEN=$(python3 -c "import json; print(json.load(open('/tmp/e2e_auth.json')).get('access_token',''))" 2>/dev/null)
if [ -n "$TOKEN" ] && [ "$TOKEN" != "" ]; then ok "Auth token obtained"; else fail "Auth failed"; exit 1; fi

AUTH="Authorization: Bearer $TOKEN"

# --- 2. Get Org ---
echo "🔹 Step 2: Fetch Organization"
HTTP=$(curl -s -o /tmp/e2e_org.json -w "%{http_code}" -H "$AUTH" "$API/orgs/current" 2>/dev/null || echo "000")
ORG_ID=$(python3 -c "import json; print(json.load(open('/tmp/e2e_org.json')).get('id',''))" 2>/dev/null)
if [ "$HTTP" = "200" ] && [ -n "$ORG_ID" ]; then ok "Org loaded: $ORG_ID (HTTP $HTTP)"; else fail "Org fetch failed (HTTP $HTTP)"; exit 1; fi

# --- 3. List Projects ---
echo "🔹 Step 3: List Projects"
HTTP=$(curl -s -o /tmp/e2e_projects.json -w "%{http_code}" -H "$AUTH" "$API/projects?org_id=$ORG_ID" 2>/dev/null || echo "000")
if [ "$HTTP" = "200" ]; then ok "Projects listed (HTTP $HTTP)"; else fail "Projects list failed (HTTP $HTTP)"; fi

# --- 4. Analyze Excel ---
echo "🔹 Step 4: Analyze Excel (sample questionnaire)"
if [ ! -f "$SAMPLE" ]; then fail "Sample file not found: $SAMPLE"; exit 1; fi

HTTP=$(curl -s -o /tmp/e2e_analyze.json -w "%{http_code}" \
  -X POST "$API/analyze-excel" \
  -H "$AUTH" \
  -F "file=@${SAMPLE}" \
  -F "org_id=${ORG_ID}" 2>/dev/null || echo "000")

STATUS=$(python3 -c "import json; print(json.load(open('/tmp/e2e_analyze.json')).get('status',''))" 2>/dev/null)
RUN_ID=$(python3 -c "import json; print(json.load(open('/tmp/e2e_analyze.json')).get('run_id',''))" 2>/dev/null)
Q_COUNT=$(python3 -c "import json; print(len(json.load(open('/tmp/e2e_analyze.json')).get('data',[])))" 2>/dev/null)

if [ "$HTTP" = "200" ] && [ "$STATUS" = "success" ]; then
    ok "Analysis complete (HTTP $HTTP, status=$STATUS, questions=$Q_COUNT, run_id=$RUN_ID)"
else
    fail "Analysis failed (HTTP $HTTP, status=$STATUS)"
    python3 -c "import json; print(json.dumps(json.load(open('/tmp/e2e_analyze.json')), indent=2)[:500])" 2>/dev/null || true
fi

# --- 5. List Runs ---
echo "🔹 Step 5: List Runs"
HTTP=$(curl -s -o /tmp/e2e_runs.json -w "%{http_code}" -H "$AUTH" "$API/runs?org_id=$ORG_ID" 2>/dev/null || echo "000")
if [ "$HTTP" = "200" ]; then ok "Runs listed (HTTP $HTTP)"; else fail "Runs list failed (HTTP $HTTP)"; fi

# --- 6. Generate Export ---
echo "🔹 Step 6: Generate Excel Export"
ANSWERS_JSON=$(python3 -c "
import json
data = json.load(open('/tmp/e2e_analyze.json')).get('data', [])
print(json.dumps(data))
" 2>/dev/null)

HTTP=$(curl -s -o /tmp/e2e_export.xlsx -w "%{http_code}" \
  -X POST "$API/generate-excel" \
  -H "$AUTH" \
  -F "file=@${SAMPLE}" \
  -F "answers_json=${ANSWERS_JSON}" \
  -F "org_id=${ORG_ID}" \
  -F "run_id=${RUN_ID}" 2>/dev/null || echo "000")

if [ "$HTTP" = "200" ]; then
    SIZE=$(wc -c < /tmp/e2e_export.xlsx | tr -d ' ')
    if [ "$SIZE" -gt 100 ]; then ok "Export generated (HTTP $HTTP, size=${SIZE}b)"; else fail "Export too small (${SIZE}b)"; fi
else
    fail "Export failed (HTTP $HTTP)"
fi

# --- 7. Audit Log ---
echo "🔹 Step 7: Audit Log"
HTTP=$(curl -s -o /tmp/e2e_audit.json -w "%{http_code}" -H "$AUTH" "$API/audit/events?org_id=$ORG_ID&limit=5" 2>/dev/null || echo "000")
if [ "$HTTP" = "200" ]; then ok "Audit log accessible (HTTP $HTTP)"; else fail "Audit log failed (HTTP $HTTP)"; fi

# --- 8. Health Deep ---
echo "🔹 Step 8: Deep Health"
HTTP=$(curl -s -o /tmp/e2e_deep.json -w "%{http_code}" -H "$AUTH" "$API/health/deep" 2>/dev/null || echo "000")
if [ "$HTTP" = "200" ]; then ok "Deep health OK (HTTP $HTTP)"; else fail "Deep health failed (HTTP $HTTP — may be OK if billing disabled)"; fi

# --- Summary ---
echo ""
echo "========================================"
echo "  Results: ✅ $PASS passed, ❌ $FAIL failed"
echo "========================================"

if [ "$FAIL" -gt 0 ]; then exit 1; else exit 0; fi
