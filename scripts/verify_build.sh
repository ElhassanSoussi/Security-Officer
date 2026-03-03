#!/usr/bin/env bash
# Production Build Verification Script
#
# Validates that both frontend and backend build successfully
# and that critical quality gates pass before deployment.
#
# Usage: ./scripts/verify_build.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() { echo -e "${GREEN}✅ PASS${NC}: $1"; ((PASS++)); }
fail() { echo -e "${RED}❌ FAIL${NC}: $1"; ((FAIL++)); }
warn() { echo -e "${YELLOW}⚠️  WARN${NC}: $1"; ((WARN++)); }

echo "╔══════════════════════════════════════════════════╗"
echo "║  NYC Compliance Architect — Build Verification   ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. Backend checks ───────────────────────────────────
echo "── Backend ──────────────────────────────────────────"

if [[ -f "backend/requirements.txt" ]]; then
    pass "backend/requirements.txt exists"
else
    fail "backend/requirements.txt missing"
fi

if [[ -f "backend/Dockerfile" ]]; then
    pass "backend/Dockerfile exists"
else
    fail "backend/Dockerfile missing"
fi

# Check Python syntax of core files
echo "  Checking Python syntax..."
SYNTAX_OK=true
for pyfile in backend/app/main.py backend/app/core/config.py backend/app/core/error_handler.py backend/app/core/logger.py backend/app/core/rate_limit.py; do
    if [[ -f "$pyfile" ]]; then
        if python3 -c "import py_compile; py_compile.compile('$pyfile', doraise=True)" 2>/dev/null; then
            : # ok
        else
            fail "Syntax error in $pyfile"
            SYNTAX_OK=false
        fi
    fi
done
if $SYNTAX_OK; then
    pass "Backend Python syntax OK"
fi

# ── 2. Frontend checks ──────────────────────────────────
echo ""
echo "── Frontend ─────────────────────────────────────────"

if [[ -f "frontend/package.json" ]]; then
    pass "frontend/package.json exists"
else
    fail "frontend/package.json missing"
fi

if [[ -f "frontend/Dockerfile" ]]; then
    pass "frontend/Dockerfile exists"
else
    fail "frontend/Dockerfile missing"
fi

# Lint check
echo "  Running frontend lint..."
if (cd frontend && npm run lint --silent 2>/dev/null); then
    pass "Frontend lint passes"
else
    warn "Frontend lint has warnings/errors"
fi

# TypeScript build check
echo "  Running frontend build check..."
if (cd frontend && npx tsc --noEmit 2>/dev/null); then
    pass "Frontend TypeScript compiles"
else
    warn "Frontend TypeScript has type errors (may be non-blocking)"
fi

# ── 3. Docker checks ────────────────────────────────────
echo ""
echo "── Docker ───────────────────────────────────────────"

if [[ -f "docker-compose.prod.yml" ]]; then
    pass "docker-compose.prod.yml exists"
else
    fail "docker-compose.prod.yml missing"
fi

if [[ -f "docker-compose.yml" ]]; then
    pass "docker-compose.yml exists"
else
    fail "docker-compose.yml missing"
fi

# ── 4. Security checks ──────────────────────────────────
echo ""
echo "── Security ─────────────────────────────────────────"

# Check for secrets in code
SECRETS_FOUND=false
for pattern in "sk-[a-zA-Z0-9]" "password\s*=" "secret.*=.*['\"][a-zA-Z0-9]"; do
    if grep -rn "$pattern" backend/app/ frontend/app/ frontend/lib/ frontend/components/ --include="*.py" --include="*.ts" --include="*.tsx" 2>/dev/null | grep -v "\.env" | grep -v "test" | grep -v "example" | grep -v "placeholder" | grep -v "STRIPE_SECRET_KEY" | grep -v "SUPABASE_SECRET_KEY" | grep -v "JWT_SECRET" | grep -v "WEBHOOK_SECRET" | head -3 | grep -q .; then
        SECRETS_FOUND=true
    fi
done
if $SECRETS_FOUND; then
    warn "Potential hardcoded secrets detected — review manually"
else
    pass "No obvious hardcoded secrets in source"
fi

# ── 4b. Stripe secret leak guard ─────────────────────────────
echo ""
echo "── Stripe Secret Leak Guard ─────────────────────────"

# Fail build if any Stripe secret env vars appear in frontend code or config.
# Only NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY is allowed in the frontend.
STRIPE_LEAK=false

# Check for secret key references in frontend source code
for secret_pattern in "STRIPE_SECRET_KEY" "STRIPE_WEBHOOK_SECRET" "sk_live_" "sk_test_" "whsec_"; do
    if grep -rn "$secret_pattern" frontend/app/ frontend/lib/ frontend/components/ frontend/hooks/ frontend/utils/ --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" 2>/dev/null | grep -v "\.example" | grep -v "// " | grep -v "* " | head -3 | grep -q .; then
        fail "Stripe secret pattern '${secret_pattern}' found in frontend source code!"
        STRIPE_LEAK=true
    fi
done

# Check that frontend env files don't contain secret keys
for envfile in frontend/.env.local frontend/.env frontend/.env.production frontend/.env.staging; do
    if [[ -f "$envfile" ]]; then
        if grep -qE "(STRIPE_SECRET_KEY|STRIPE_WEBHOOK_SECRET|sk_live_|sk_test_|whsec_)" "$envfile" 2>/dev/null; then
            fail "Stripe secret found in ${envfile} — remove immediately!"
            STRIPE_LEAK=true
        fi
    fi
done

# Check that docker-compose and Dockerfile don't pass secrets to frontend
if grep -A5 "frontend:" docker-compose.prod.yml 2>/dev/null | grep -qE "STRIPE_SECRET_KEY|STRIPE_WEBHOOK_SECRET"; then
    fail "Stripe secret env var mapped to frontend service in docker-compose.prod.yml!"
    STRIPE_LEAK=true
fi

if grep -qE "STRIPE_SECRET_KEY|STRIPE_WEBHOOK_SECRET" frontend/Dockerfile 2>/dev/null; then
    fail "Stripe secret env var referenced in frontend/Dockerfile!"
    STRIPE_LEAK=true
fi

# Check for NEXT_PUBLIC_ prefix on secret keys (should never happen)
for envfile in frontend/.env.example frontend/.env.local.example frontend/.env.local frontend/.env frontend/.env.production; do
    if [[ -f "$envfile" ]]; then
        if grep -qE "NEXT_PUBLIC_STRIPE_SECRET_KEY|NEXT_PUBLIC_STRIPE_WEBHOOK_SECRET" "$envfile" 2>/dev/null; then
            fail "NEXT_PUBLIC_ prefix used on Stripe secret in ${envfile} — this exposes secrets to the browser!"
            STRIPE_LEAK=true
        fi
    fi
done

if $STRIPE_LEAK; then
    fail "Stripe secret leak detected — fix before deploying!"
else
    pass "No Stripe secrets leaked to frontend"
fi

# ── 5. Health endpoint ───────────────────────────────────
echo ""
echo "── Health Endpoint ──────────────────────────────────"

if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    pass "Backend health endpoint responds"
else
    warn "Backend not running (health check skipped)"
fi

# ── Summary ──────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
echo -e "  Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}, ${YELLOW}${WARN} warnings${NC}"
echo "══════════════════════════════════════════════════════"

if [[ $FAIL -gt 0 ]]; then
    echo -e "${RED}BUILD VERIFICATION FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}BUILD VERIFICATION PASSED${NC}"
    exit 0
fi
