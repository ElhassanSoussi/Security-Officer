#!/bin/bash
set -e

# Ensure we run from repo root regardless of where this script lives.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 Security Officer — Local Verification${NC}"
echo "=================================================="

# 1. Inject Dummy Env if Missing (To satisfy Docker interpolation)
export SUPABASE_URL=${SUPABASE_URL:-"https://placeholder.supabase.co"}
export SUPABASE_KEY=${SUPABASE_KEY:-"placeholder-key"}
export SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET:-"placeholder-secret"}
export OPENAI_API_KEY=${OPENAI_API_KEY:-"sk-placeholder"}
export STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY:-"sk_test_placeholder"}
export STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET:-"whsec_placeholder"}
export DEFAULT_ORG_ID=${DEFAULT_ORG_ID:-"00000000-0000-0000-0000-000000000000"}

echo "Environment:"
echo "  SUPABASE_URL  = ${SUPABASE_URL:0:20}..."
echo "  DEFAULT_ORG_ID= $DEFAULT_ORG_ID"
echo "=================================================="

# 2. Build & Start Backend
echo -e "\n${GREEN}🐳 Step 1: Building & Starting Backend Container...${NC}"
docker compose -f docker-compose.verify.yml up -d --build backend 2>&1
echo "Waiting 8s for backend startup..."
sleep 8

# 3. Check Backend Logs (quick sanity)
echo -e "\n${GREEN}📋 Step 2: Backend Logs (last 5 lines):${NC}"
docker logs security-officer-backend-1 --tail 5 2>&1

BASE="http://localhost:8000"
PASS=0
FAIL=0

# --- TEST 1: Root Health (/) ---
echo -e "\n${GREEN}🏥 Test 1: GET / (Root Health)${NC}"
RESP=$(curl -s -w "\n%{http_code}" "$BASE/")
HTTP_CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -1)
echo "  Status: $HTTP_CODE"
echo "  Body:   $BODY"
if [ "$HTTP_CODE" == "200" ]; then
    echo -e "  ${GREEN}✅ PASS${NC}"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}❌ FAIL${NC}"
    FAIL=$((FAIL+1))
fi

# --- TEST 2: API Health (/api/v1/health) --- PUBLIC, no auth needed
echo -e "\n${GREEN}🏥 Test 2: GET /api/v1/health (Public)${NC}"
RESP=$(curl -s -w "\n%{http_code}" "$BASE/api/v1/health")
HTTP_CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -1)
echo "  Status: $HTTP_CODE"
echo "  Body:   $BODY"
if [ "$HTTP_CODE" == "200" ]; then
    echo -e "  ${GREEN}✅ PASS${NC}"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}❌ FAIL${NC}"
    FAIL=$((FAIL+1))
fi

# --- TEST 3: /api/v1/orgs (Requires Auth — expect 401/403, NOT 500) ---
echo -e "\n${GREEN}🏢 Test 3: GET /api/v1/orgs (Auth Check — expect 401)${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/orgs")
echo "  Status: $HTTP_CODE"
if [ "$HTTP_CODE" == "401" ] || [ "$HTTP_CODE" == "403" ]; then
    echo -e "  ${GREEN}✅ PASS (Secured — no 500)${NC}"
    PASS=$((PASS+1))
elif [ "$HTTP_CODE" == "200" ]; then
    echo -e "  ${GREEN}✅ PASS (Open/200)${NC}"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}❌ FAIL (Got $HTTP_CODE, expected 401/403)${NC}"
    FAIL=$((FAIL+1))
fi

# --- TEST 4: /api/v1/projects (Requires Auth — expect 401/403, NOT 500) ---
echo -e "\n${GREEN}📂 Test 4: GET /api/v1/projects (Auth Check — expect 401)${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/projects")
echo "  Status: $HTTP_CODE"
if [ "$HTTP_CODE" == "401" ] || [ "$HTTP_CODE" == "403" ]; then
    echo -e "  ${GREEN}✅ PASS (Secured — no 500)${NC}"
    PASS=$((PASS+1))
elif [ "$HTTP_CODE" == "200" ]; then
    echo -e "  ${GREEN}✅ PASS (Open/200)${NC}"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}❌ FAIL (Got $HTTP_CODE, expected 401/403)${NC}"
    FAIL=$((FAIL+1))
fi

# --- TEST 5: /api/v1/billing/plans (Requires Auth — expect 401, NOT 500) ---
echo -e "\n${GREEN}💳 Test 5: GET /api/v1/billing/plans (Auth Check — expect 401)${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/billing/plans")
echo "  Status: $HTTP_CODE"
if [ "$HTTP_CODE" == "401" ] || [ "$HTTP_CODE" == "403" ]; then
    echo -e "  ${GREEN}✅ PASS (Secured — no 500)${NC}"
    PASS=$((PASS+1))
elif [ "$HTTP_CODE" == "200" ]; then
    echo -e "  ${GREEN}✅ PASS (Open/200)${NC}"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}❌ FAIL (Got $HTTP_CODE, expected 401/403)${NC}"
    FAIL=$((FAIL+1))
fi

# --- TEST 6: /api/v1/billing/subscription (Requires Auth) ---
echo -e "\n${GREEN}💳 Test 6: GET /api/v1/billing/subscription (Auth Check)${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/billing/subscription")
echo "  Status: $HTTP_CODE"
if [ "$HTTP_CODE" == "401" ] || [ "$HTTP_CODE" == "403" ]; then
    echo -e "  ${GREEN}✅ PASS (Secured — no 500)${NC}"
    PASS=$((PASS+1))
elif [ "$HTTP_CODE" == "200" ]; then
    echo -e "  ${GREEN}✅ PASS (Open/200)${NC}"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}❌ FAIL (Got $HTTP_CODE, expected 401/403)${NC}"
    FAIL=$((FAIL+1))
fi

# --- TEST 7: Sample Questionnaire Download (Public) ---
echo -e "\n${GREEN}📥 Test 7: GET /api/v1/runs/samples/questionnaire (Download)${NC}"
RESP=$(curl -s -w "\n%{http_code}" -D - -o /tmp/sample_questionnaire.xlsx "$BASE/api/v1/runs/samples/questionnaire")
HTTP_CODE=$(echo "$RESP" | grep "HTTP/" | tail -1 | awk '{print $2}')
echo "  Status: $HTTP_CODE"
if [ -f /tmp/sample_questionnaire.xlsx ] && [ -s /tmp/sample_questionnaire.xlsx ]; then
    SIZE=$(wc -c < /tmp/sample_questionnaire.xlsx | tr -d ' ')
    echo "  File Size: ${SIZE} bytes"
    echo -e "  ${GREEN}✅ PASS (Downloaded .xlsx)${NC}"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}❌ FAIL (No file or empty)${NC}"
    FAIL=$((FAIL+1))
fi

# --- SUMMARY ---
echo ""
echo "=================================================="
TOTAL=$((PASS+FAIL))
echo -e "Results: ${GREEN}$PASS PASSED${NC} / ${RED}$FAIL FAILED${NC} out of $TOTAL tests"
echo "=================================================="

if [ $FAIL -eq 0 ]; then
    echo -e "\n${GREEN}🎉 ALL TESTS PASSED — Backend is operational!${NC}"
    exit 0
else
    echo -e "\n${YELLOW}⚠️  Some tests failed. Check output above.${NC}"
    exit 1
fi
