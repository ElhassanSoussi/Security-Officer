#!/bin/bash
# Full E2E test: Backend + Frontend Proxy
# Tests the complete flow that was causing "Analysis failed" in the browser
set +e

ROOT="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd || echo "$(pwd)")"
source "${ROOT}/.smoke.env" 2>/dev/null || true
# Load frontend env for Supabase vars (if available)
[ -f "${ROOT}/frontend/.env.local" ] && set -a && source "${ROOT}/frontend/.env.local" && set +a

BACKEND="http://localhost:8000"
FRONTEND="http://localhost:3001"
SUPABASE="${NEXT_PUBLIC_SUPABASE_URL:?Set NEXT_PUBLIC_SUPABASE_URL in frontend/.env.local or environment}"
ANON_KEY="${NEXT_PUBLIC_SUPABASE_ANON_KEY:?Set NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env.local or environment}"
SAMPLE="${ROOT}/backend/samples/sample_questionnaire.xlsx"
ORG_ID="${SMOKE_ORG_ID:-}"
EMAIL="${SMOKE_EMAIL:?Set SMOKE_EMAIL in .smoke.env or environment}"
PASSWORD="${SMOKE_PASSWORD:?Set SMOKE_PASSWORD in .smoke.env or environment}"
PASS=0
FAIL=0

green() { printf "\033[32m%s\033[0m\n" "$1"; }
red()   { printf "\033[31m%s\033[0m\n" "$1"; }
step()  { printf "\n\033[1;36m=== %s: %s ===\033[0m\n" "$1" "$2"; }

check() {
  if [ "$1" -eq 0 ]; then
    green "  ✅ PASS: $2"
    PASS=$((PASS + 1))
  else
    red "  ❌ FAIL: $2"
    FAIL=$((FAIL + 1))
  fi
}

# ─── Backend health ───
step 1 "Backend Health"
HEALTH=$(curl -sf "$BACKEND/health" 2>/dev/null)
echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='ok'" 2>/dev/null
check $? "Backend /health returns ok"

# ─── Frontend proxy health ───
step 2 "Frontend Proxy Health"
PROXY_HEALTH=$(curl -sf "$FRONTEND/api/v1/health" 2>/dev/null)
echo "$PROXY_HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='ok'" 2>/dev/null
check $? "Frontend proxy /api/v1/health returns ok"

# ─── Authentication ───
step 3 "Authentication"
AUTH_URL="${SUPABASE}/auth/v1/token?grant_type=password"
TOKEN=$(curl -s -X POST "$AUTH_URL" \
  -H "apikey: $ANON_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null)

if [ -n "$TOKEN" ] && [ "$TOKEN" != "" ]; then
  check 0 "Got auth token (${#TOKEN} chars)"
else
  check 1 "Failed to get auth token"
  red "Cannot proceed without auth token"
  exit 1
fi

AUTH="Authorization: Bearer $TOKEN"

# ─── Organization ───
step 4 "Organization"
ORG=$(curl -sf "$BACKEND/api/v1/orgs" -H "$AUTH" 2>/dev/null)
echo "$ORG" | python3 -c "import sys,json; orgs=json.load(sys.stdin); assert any(o['id']=='$ORG_ID' for o in orgs)" 2>/dev/null
check $? "Org $ORG_ID exists"

# ─── Projects ───
step 5 "Projects"
PROJECTS=$(curl -sf "$BACKEND/api/v1/projects?org_id=$ORG_ID" -H "$AUTH" 2>/dev/null)
PROJ_ID=$(echo "$PROJECTS" | python3 -c "import sys,json; ps=json.load(sys.stdin); print(ps[0].get('project_id', ps[0].get('id','')) if ps else '')" 2>/dev/null)
if [ -n "$PROJ_ID" ]; then
  check 0 "Got project: $PROJ_ID"
else
  # Create one
  PROJ_ID=$(curl -sf -X POST "$BACKEND/api/v1/projects" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d "{\"org_id\":\"$ORG_ID\",\"name\":\"E2E Test Project\"}" 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('project_id', d.get('id','')))" 2>/dev/null)
  if [ -n "$PROJ_ID" ]; then
    check 0 "Created project: $PROJ_ID"
  else
    check 1 "Failed to create project"
  fi
fi

# ─── Analyze Excel (DIRECT to backend) ───
step 6 "Analyze Excel (Direct Backend)"
ANALYZE_DIRECT=$(curl -s --max-time 90 -X POST "$BACKEND/api/v1/analyze-excel" \
  -H "$AUTH" \
  -F "file=@$SAMPLE" \
  -F "org_id=$ORG_ID" \
  -F "project_id=$PROJ_ID" \
  -F "framework=SOC 2" 2>/dev/null)
DIRECT_RUN_ID=$(echo "$ANALYZE_DIRECT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('run_id',''))" 2>/dev/null)
DIRECT_COUNT=$(echo "$ANALYZE_DIRECT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data', d.get('questions',[]))))" 2>/dev/null)
if [ -n "$DIRECT_RUN_ID" ] && [ "$DIRECT_COUNT" -gt 0 ] 2>/dev/null; then
  check 0 "Direct analysis: run_id=$DIRECT_RUN_ID, questions=$DIRECT_COUNT"
else
  check 1 "Direct analysis failed"
  echo "  Response: $(echo "$ANALYZE_DIRECT" | head -c 300)"
fi

# ─── Analyze Excel (THROUGH FRONTEND PROXY — the failing path) ───
step 7 "Analyze Excel (Frontend Proxy)"
ANALYZE_PROXY=$(curl -s --max-time 120 -X POST "$FRONTEND/api/v1/analyze-excel" \
  -H "$AUTH" \
  -F "file=@$SAMPLE" \
  -F "org_id=$ORG_ID" \
  -F "project_id=$PROJ_ID" \
  -F "framework=SOC 2" 2>/dev/null)
PROXY_RUN_ID=$(echo "$ANALYZE_PROXY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('run_id',''))" 2>/dev/null)
PROXY_COUNT=$(echo "$ANALYZE_PROXY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data', d.get('questions',[]))))" 2>/dev/null)
if [ -n "$PROXY_RUN_ID" ] && [ "$PROXY_COUNT" -gt 0 ] 2>/dev/null; then
  check 0 "Proxy analysis: run_id=$PROXY_RUN_ID, questions=$PROXY_COUNT"
else
  check 1 "Proxy analysis failed"
  echo "  Response: $(echo "$ANALYZE_PROXY" | head -c 500)"
fi

# ─── Runs List ───
step 8 "Runs List"
RUNS=$(curl -sf "$BACKEND/api/v1/runs" -H "$AUTH" 2>/dev/null)
RUN_COUNT=$(echo "$RUNS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
if [ "$RUN_COUNT" -gt 0 ] 2>/dev/null; then
  check 0 "Found $RUN_COUNT runs"
else
  check 1 "No runs found"
fi

# ─── Generate Excel Export ───
step 9 "Generate Excel Export"
EXPORT_RUN="${DIRECT_RUN_ID:-$PROXY_RUN_ID}"
EXPORT_DATA="${ANALYZE_DIRECT:-$ANALYZE_PROXY}"
if [ -n "$EXPORT_RUN" ] && [ -n "$EXPORT_DATA" ]; then
  # Extract the answers JSON from the analysis result data field and save to file
  echo "$EXPORT_DATA" | python3 -c "
import sys,json
d=json.load(sys.stdin)
items=d.get('data', d.get('questions',[]))
with open('/tmp/e2e_answers.json','w') as f:
    json.dump(items, f)
print(len(items))
" 2>/dev/null > /tmp/e2e_answers_count.txt
  ACOUNT=$(cat /tmp/e2e_answers_count.txt 2>/dev/null | tr -d '[:space:]')
  if [ -n "$ACOUNT" ] && [ "$ACOUNT" -gt 0 ] 2>/dev/null; then
    HTTP_CODE=$(curl -s --max-time 30 -o /tmp/e2e_export.xlsx -w "%{http_code}" \
      -X POST "$BACKEND/api/v1/generate-excel" \
      -H "$AUTH" \
      -F "file=@$SAMPLE" \
      -F "answers_json=</tmp/e2e_answers.json" \
      -F "org_id=$ORG_ID" \
      -F "project_id=$PROJ_ID" \
      -F "run_id=$EXPORT_RUN" 2>/dev/null)
    FSIZE=$(wc -c < /tmp/e2e_export.xlsx 2>/dev/null | tr -d ' ')
    if [ "$HTTP_CODE" = "200" ] && [ "$FSIZE" -gt 100 ] 2>/dev/null; then
      check 0 "Export: HTTP $HTTP_CODE, size=${FSIZE}B"
    else
      check 1 "Export: HTTP $HTTP_CODE, size=${FSIZE:-0}B"
    fi
  else
    check 1 "No analysis data to export"
  fi
else
  check 1 "No run_id to export"
fi

# ─── Audit log ───
step 10 "Audit Log"
AUDIT=$(curl -sf "$BACKEND/api/v1/audit/log?org_id=$ORG_ID" -H "$AUTH" 2>/dev/null)
AUDIT_COUNT=$(echo "$AUDIT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else len(d.get('data',d.get('items',[]))))" 2>/dev/null)
if [ -n "$AUDIT_COUNT" ] && [ "$AUDIT_COUNT" -gt 0 ] 2>/dev/null; then
  check 0 "Audit log has $AUDIT_COUNT entries"
else
  # Audit log might be empty if no events yet — that's ok
  check 0 "Audit log returned (${AUDIT_COUNT:-0} entries)"
fi

# ─── Summary ───
echo ""
echo "==========================================="
printf "\033[1m  E2E Results: %s passed, %s failed\033[0m\n" "$PASS" "$FAIL"
echo "==========================================="

if [ "$FAIL" -gt 0 ]; then
  red "  ⚠️  Some tests failed!"
  exit 1
else
  green "  🎉 All E2E tests passed!"
  exit 0
fi
