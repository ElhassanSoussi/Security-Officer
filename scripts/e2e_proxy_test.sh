#!/bin/bash
# E2E test through the frontend proxy
# Saves all output to /tmp/e2e_results.txt
set -e

OUTFILE="/tmp/e2e_results.txt"
BACKEND="http://localhost:8000"
FRONTEND="http://localhost:3001"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Load env files for secrets (never hardcoded)
source "${ROOT}/.smoke.env" 2>/dev/null || true
[ -f "${ROOT}/frontend/.env.local" ] && set -a && source "${ROOT}/frontend/.env.local" && set +a
SUPABASE="${NEXT_PUBLIC_SUPABASE_URL:?Set NEXT_PUBLIC_SUPABASE_URL in frontend/.env.local or environment}"
ANON_KEY="${NEXT_PUBLIC_SUPABASE_ANON_KEY:?Set NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env.local or environment}"
SAMPLE="${ROOT}/backend/samples/sample_questionnaire.xlsx"
ORG_ID="${SMOKE_ORG_ID:-}"

echo "=== E2E TEST $(date) ===" > "$OUTFILE"

# Backend health
echo "" >> "$OUTFILE"
echo "--- Backend Health ---" >> "$OUTFILE"
HEALTH=$(curl -s --max-time 10 "$BACKEND/health" 2>&1)
echo "$HEALTH" >> "$OUTFILE"
echo "$HEALTH" | grep -q '"status":"ok"' && echo "PASS: Backend healthy" >> "$OUTFILE" || echo "FAIL: Backend unhealthy" >> "$OUTFILE"

# Frontend Proxy Health
echo "" >> "$OUTFILE"
echo "--- Frontend Proxy Health ---" >> "$OUTFILE"
PROXY_HEALTH=$(curl -s --max-time 30 "$FRONTEND/api/v1/health" 2>&1)
echo "$PROXY_HEALTH" >> "$OUTFILE"
echo "$PROXY_HEALTH" | grep -q '"status":"ok"' && echo "PASS: Proxy working" >> "$OUTFILE" || echo "FAIL: Proxy broken" >> "$OUTFILE"

# Auth
echo "" >> "$OUTFILE"
echo "--- Auth ---" >> "$OUTFILE"
SMOKE_EMAIL="${SMOKE_EMAIL:?Set SMOKE_EMAIL in .smoke.env or environment}"
SMOKE_PASSWORD="${SMOKE_PASSWORD:?Set SMOKE_PASSWORD in .smoke.env or environment}"
AUTH_RESP=$(curl -s --max-time 15 "${SUPABASE}/auth/v1/token?grant_type=password" \
  -H "apikey: ${ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${SMOKE_EMAIL}\",\"password\":\"${SMOKE_PASSWORD}\"}" 2>&1)
TOKEN=$(echo "$AUTH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")
if [ -n "$TOKEN" ]; then
  echo "PASS: Got auth token (${#TOKEN} chars)" >> "$OUTFILE"
else
  echo "FAIL: No auth token" >> "$OUTFILE"
  echo "$AUTH_RESP" >> "$OUTFILE"
fi

# Direct Backend Analyze
echo "" >> "$OUTFILE"
echo "--- Direct Backend Analyze ---" >> "$OUTFILE"
if [ -n "$TOKEN" ] && [ -f "$SAMPLE" ]; then
  ANALYZE_DIRECT=$(curl -s --max-time 120 "$BACKEND/api/v1/analyze-excel" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@${SAMPLE}" \
    -F "org_id=${ORG_ID}" 2>&1)
  echo "$ANALYZE_DIRECT" | head -c 500 >> "$OUTFILE"
  echo "" >> "$OUTFILE"
  echo "$ANALYZE_DIRECT" | grep -q '"run_id"' && echo "PASS: Direct analysis works" >> "$OUTFILE" || echo "FAIL: Direct analysis failed" >> "$OUTFILE"
else
  echo "SKIP: No token or sample file" >> "$OUTFILE"
fi

# Proxy analyze-excel (the critical test!)
echo "" >> "$OUTFILE"
echo "--- Proxy Analyze (THE FIX TEST) ---" >> "$OUTFILE"
if [ -n "$TOKEN" ] && [ -f "$SAMPLE" ]; then
  ANALYZE_PROXY=$(curl -s --max-time 120 "$FRONTEND/api/v1/analyze-excel" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@${SAMPLE}" \
    -F "org_id=${ORG_ID}" 2>&1)
  echo "$ANALYZE_PROXY" | head -c 500 >> "$OUTFILE"
  echo "" >> "$OUTFILE"
  echo "$ANALYZE_PROXY" | grep -q '"run_id"' && echo "PASS: PROXY ANALYSIS WORKS!" >> "$OUTFILE" || echo "FAIL: Proxy analysis failed" >> "$OUTFILE"
else
  echo "SKIP: No token or sample file" >> "$OUTFILE"
fi

# Step 6: List runs
echo "" >> "$OUTFILE"
echo "--- STEP 6: List Runs ---" >> "$OUTFILE"
if [ -n "$TOKEN" ]; then
  RUNS=$(curl -s --max-time 15 "$FRONTEND/api/v1/runs" \
    -H "Authorization: Bearer $TOKEN" 2>&1)
  RUN_COUNT=$(echo "$RUNS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else 0)" 2>/dev/null || echo "0")
  echo "Runs found: $RUN_COUNT" >> "$OUTFILE"
  echo "$RUNS" | head -c 300 >> "$OUTFILE"
  echo "" >> "$OUTFILE"
  [ "$RUN_COUNT" -gt "0" ] && echo "PASS: Runs listed" >> "$OUTFILE" || echo "WARN: No runs found (might be ok)" >> "$OUTFILE"
fi

# Step 7: Frontend page loads
echo "" >> "$OUTFILE"
echo "--- STEP 7: Frontend Pages ---" >> "$OUTFILE"
for PAGE in "/" "/run" "/security"; do
  HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "${FRONTEND}${PAGE}" 2>/dev/null)
  echo "  ${PAGE} => HTTP $HTTP_CODE" >> "$OUTFILE"
done

echo "" >> "$OUTFILE"
echo "=== E2E TEST COMPLETE $(date) ===" >> "$OUTFILE"
echo "Results saved to $OUTFILE"
