#!/usr/bin/env bash
# ==============================================================================
# scripts/scan_secrets.sh — Pre-push secrets scanner
# ==============================================================================
# Scans tracked files for patterns that should never be committed.
# Exits non-zero if any potential secrets are found.
#
# Usage:
#   ./scripts/scan_secrets.sh            # scan all tracked files
#   ./scripts/scan_secrets.sh --staged   # scan only staged files (for pre-commit hook)
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# ── Determine file list ──────────────────────────────────────────────────────
if [[ "${1:-}" == "--staged" ]]; then
    FILES=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || true)
    SCOPE="staged files"
else
    FILES=$(git ls-files 2>/dev/null || find . -type f -not -path './.git/*' -not -path '*/node_modules/*' -not -path '*/venv*/*' -not -path '*/.next/*')
    SCOPE="all tracked files"
fi

if [[ -z "$FILES" ]]; then
    echo -e "${GREEN}✓ No files to scan${NC}"
    exit 0
fi

# ── Patterns that indicate leaked secrets ────────────────────────────────────
# Each entry: "LABEL:::REGEX"
PATTERNS=(
    "OpenAI API Key:::sk-[A-Za-z0-9_-]{20,}"
    "Supabase Service Role Key:::service_role['\"]?\s*[:=]\s*['\"]?eyJ"
    "Supabase Key (raw JWT):::SUPABASE_KEY\s*=\s*eyJ"
    "Supabase Service Role (raw JWT):::SUPABASE_SERVICE_ROLE_KEY\s*=\s*eyJ"
    "Supabase Secret (raw JWT):::SUPABASE_SECRET_KEY\s*=\s*eyJ"
    "Supabase JWT Secret (raw):::SUPABASE_JWT_SECRET\s*=\s*[A-Za-z0-9+/=]{20,}"
    "Stripe Secret Key:::sk_live_[A-Za-z0-9]{20,}"
    "Stripe Test Key (long):::sk_test_[A-Za-z0-9]{24,}"
    "Stripe Webhook Secret:::whsec_[A-Za-z0-9]{20,}"
    "Generic Private Key:::-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
    "OpenAI Org Key:::org-[A-Za-z0-9]{20,}"
)

# ── Files/paths to always skip ───────────────────────────────────────────────
SKIP_PATTERNS=(
    "\.env\.example"
    "\.env\.local\.example"
    "scan_secrets\.sh"
    "node_modules/"
    "venv"
    "\.next/"
    "__pycache__/"
    "\.git/"
    "\.xlsx$"
    "\.png$"
    "\.ico$"
    "\.woff"
    "\.ttf$"
)

FOUND=0

for entry in "${PATTERNS[@]}"; do
    LABEL="${entry%%:::*}"
    REGEX="${entry##*:::}"

    # grep through file list, skip binary and excluded paths
    MATCHES=""
    while IFS= read -r f; do
        # Skip excluded patterns
        SKIP=false
        for sp in "${SKIP_PATTERNS[@]}"; do
            if echo "$f" | grep -qE "$sp"; then
                SKIP=true
                break
            fi
        done
        $SKIP && continue

        # Only scan text files
        [[ -f "$f" ]] || continue

        RESULT=$(grep -nE "$REGEX" "$f" 2>/dev/null || true)
        if [[ -n "$RESULT" ]]; then
            MATCHES="${MATCHES}${f}:${RESULT}\n"
        fi
    done <<< "$FILES"

    if [[ -n "$MATCHES" ]]; then
        echo -e "${RED}✗ POTENTIAL SECRET: ${LABEL}${NC}"
        echo -e "${YELLOW}${MATCHES}${NC}"
        FOUND=$((FOUND + 1))
    fi
done

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
if [[ $FOUND -gt 0 ]]; then
    echo -e "${RED}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  FAILED: Found $FOUND potential secret pattern(s) in ${SCOPE}${NC}"
    echo -e "${RED}  Remove secrets before pushing to GitHub.${NC}"
    echo -e "${RED}══════════════════════════════════════════════════════════════${NC}"
    exit 1
else
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  PASSED: No secrets detected in ${SCOPE}${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    exit 0
fi
