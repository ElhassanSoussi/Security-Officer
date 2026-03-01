#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND_BASE="${BACKEND_BASE:-http://127.0.0.1:8000}"
API_BASE="${API_BASE:-$BACKEND_BASE/api/v1}"

pass() { echo "PASS $*"; }
fail() { echo "FAIL $*" >&2; exit 1; }

need_file() {
  local p="$1"
  [ -f "$p" ] || fail "missing file: $p"
}

http_code() {
  curl -sS -o /tmp/smoke_body.$$ -w "%{http_code}" "$@"
}

json_get() {
  # Read JSON on stdin; print a top-level key value.
  python3 -c 'import json,sys; key=sys.argv[1]; obj=json.load(sys.stdin); val=obj.get(key); \
    (print(json.dumps(val)) if isinstance(val,(dict,list)) else print(val)) if val is not None else sys.exit(2)' "$1"
}

read_env_key() {
  local file="$1"
  local key="$2"
  python3 - "$file" "$key" <<'PY'
from __future__ import annotations
from pathlib import Path
import sys

path = Path(sys.argv[1])
k = sys.argv[2]
for raw in path.read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    kk, vv = line.split("=", 1)
    if kk.strip() != k:
        continue
    v = vv.strip().strip('"').strip("'")
    if v:
        print(v)
        raise SystemExit(0)
raise SystemExit(1)
PY
}

verify_xlsx() {
  local path="$1"
  python3 - "$path" <<'PY'
import sys, zipfile
p = sys.argv[1]
with open(p, "rb") as f:
    sig = f.read(4)
if sig != b"PK\x03\x04":
    raise SystemExit("not an xlsx (missing ZIP signature)")
z = zipfile.ZipFile(p)
names = set(z.namelist())
needed = {"[Content_Types].xml"}
missing = needed - names
if missing:
    raise SystemExit(f"missing xlsx parts: {sorted(missing)}")
bad = z.testzip()
if bad:
    raise SystemExit(f"corrupt zip member: {bad}")
print("ok")
PY
}

echo "Smoke: backend=$BACKEND_BASE api=$API_BASE"

# --- Basic backend checks (no auth) ---
code="$(http_code -D /tmp/smoke_h.$$ "$BACKEND_BASE/health")"
[ "$code" = "200" ] || fail "GET /health -> $code"
pass "GET /health -> 200"

code="$(http_code -D /tmp/smoke_h.$$ "$API_BASE/ready")"
[ "$code" = "200" ] || fail "GET /api/v1/ready -> $code"
ready="$(cat /tmp/smoke_body.$$ | json_get ready || echo false)"
[ "$ready" = "True" ] || [ "$ready" = "true" ] || fail "GET /api/v1/ready ready=$ready"
pass "GET /api/v1/ready -> ready=true"

code="$(curl -sS -D /tmp/smoke_h.$$ -o /tmp/sample.xlsx -w "%{http_code}" "$API_BASE/runs/samples/questionnaire")"
[ "$code" = "200" ] || fail "GET /api/v1/runs/samples/questionnaire -> $code"
ctype="$(grep -i '^content-type:' /tmp/smoke_h.$$ | tail -1 | tr -d '\r' | cut -d: -f2- | xargs || true)"
echo "$ctype" | grep -qi 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' || fail "sample content-type not xlsx: $ctype"
verify_xlsx /tmp/sample.xlsx >/dev/null || fail "sample xlsx invalid"
pass "GET /api/v1/runs/samples/questionnaire -> 200 + valid xlsx"

# --- Auth checks (Supabase password grant) ---
need_file "frontend/.env.local"
SUPABASE_URL="$(read_env_key frontend/.env.local NEXT_PUBLIC_SUPABASE_URL || true)"
SUPABASE_ANON_KEY="$(read_env_key frontend/.env.local NEXT_PUBLIC_SUPABASE_ANON_KEY || true)"
[ -n "${SUPABASE_URL:-}" ] || fail "frontend/.env.local missing NEXT_PUBLIC_SUPABASE_URL"
[ -n "${SUPABASE_ANON_KEY:-}" ] || fail "frontend/.env.local missing NEXT_PUBLIC_SUPABASE_ANON_KEY"

if [ -z "${SMOKE_EMAIL:-}" ] || [ -z "${SMOKE_PASSWORD:-}" ]; then
  if [ -f "$ROOT/.smoke.env" ]; then
    # shellcheck disable=SC1091
    set -a; source "$ROOT/.smoke.env"; set +a
  fi
fi

[ -n "${SMOKE_EMAIL:-}" ] || fail "set SMOKE_EMAIL (or run: ./scripts/smoke_setup.sh)"
[ -n "${SMOKE_PASSWORD:-}" ] || fail "set SMOKE_PASSWORD (or run: ./scripts/smoke_setup.sh)"

AUTH_JSON="$(curl -sS -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$SMOKE_EMAIL\",\"password\":\"$SMOKE_PASSWORD\"}")"

TOKEN="$(python3 -c 'import json,sys; obj=json.load(sys.stdin); tok=obj.get("access_token") or ""; \
  (print(tok) if tok else (_ for _ in ()).throw(SystemExit(obj.get("error_description") or obj.get("msg") or obj.get("error") or "no access_token")))' <<<"$AUTH_JSON")" \
  || fail "Supabase login failed (check SMOKE_EMAIL/SMOKE_PASSWORD + Supabase env)"

AUTHZ_HEADER="Authorization: Bearer $TOKEN"

# --- Org bootstrap + core authenticated endpoints ---
org_code="$(curl -sS -H "$AUTHZ_HEADER" -o /tmp/org_current.json -w "%{http_code}" "$API_BASE/orgs/current")"
if [ "$org_code" = "404" ]; then
  org_code="$(curl -sS -X POST -H "$AUTHZ_HEADER" -H "Content-Type: application/json" -o /tmp/org_current.json -w "%{http_code}" "$API_BASE/orgs/onboard" -d '{}')"
fi
[ "$org_code" = "200" ] || fail "org bootstrap -> $org_code"
ORG_ID="$(python3 - <<'PY'
import json
obj = json.load(open("/tmp/org_current.json"))
print(obj.get("id") or "")
PY
)"
[ -n "$ORG_ID" ] || fail "org bootstrap missing org id"
pass "org resolved -> $ORG_ID"

check_auth_get() {
  local name="$1"
  local url="$2"
  local code
  code="$(curl -sS -H "$AUTHZ_HEADER" -o /tmp/smoke_body.$$ -w "%{http_code}" "$url")"
  [ "$code" = "200" ] || fail "$name -> $code $(head -c 120 /tmp/smoke_body.$$ | tr '\n' ' ')"
  pass "$name -> 200"
}

check_auth_get "GET /api/v1/settings/profile" "$API_BASE/settings/profile"
check_auth_get "GET /api/v1/settings/org" "$API_BASE/settings/org?org_id=$ORG_ID"
check_auth_get "GET /api/v1/billing/plans" "$API_BASE/billing/plans"
check_auth_get "GET /api/v1/billing/subscription" "$API_BASE/billing/subscription?org_id=$ORG_ID"
check_auth_get "GET /api/v1/billing/plan" "$API_BASE/billing/plan?org_id=$ORG_ID"
check_auth_get "GET /api/v1/audit/log" "$API_BASE/audit/log?org_id=$ORG_ID&limit=1&offset=0"
check_auth_get "GET /api/v1/audit/exports" "$API_BASE/audit/exports?org_id=$ORG_ID&limit=1&offset=0"
check_auth_get "GET /api/v1/projects" "$API_BASE/projects?org_id=$ORG_ID"

# --- Run + export via API (end-to-end) ---
need_file "backend/tests/fixtures/test_questionnaire.xlsx"
an_code="$(curl -sS -X POST -H "$AUTHZ_HEADER" \
  -F "file=@backend/tests/fixtures/test_questionnaire.xlsx" \
  -F "org_id=$ORG_ID" \
  -o /tmp/analyze.json -w "%{http_code}" \
  "$API_BASE/analyze-excel")"
[ "$an_code" = "200" ] || fail "POST /api/v1/analyze-excel -> $an_code"

RUN_ID="$(python3 - <<'PY'
import json
obj = json.load(open("/tmp/analyze.json"))
print(obj.get("run_id") or "")
PY
)"
[ -n "$RUN_ID" ] || fail "analyze-excel missing run_id"
pass "POST /api/v1/analyze-excel -> 200 run_id=$RUN_ID"

python3 - <<'PY'
import json
obj = json.load(open("/tmp/analyze.json"))
items = obj.get("data") or []
out = []
for it in items[:50]:  # keep it bounded
    out.append({
        "sheet_name": it.get("sheet_name") or "Sheet1",
        "cell_coordinate": it.get("cell_coordinate") or it.get("cell_reference") or "A1",
        "question": it.get("question") or "",
        "ai_answer": it.get("ai_answer") or "",
        "final_answer": it.get("final_answer") or it.get("ai_answer") or "",
        "confidence": it.get("confidence") or "LOW",
        "sources": it.get("sources") or [],
        "is_verified": bool(it.get("is_verified") or False),
        "edited_by_user": bool(it.get("edited_by_user") or False),
        "status": it.get("status"),
        "status_reason": it.get("status_reason"),
    })
open("/tmp/answers.json", "w").write(json.dumps(out, separators=(",", ":")))
PY

ex_code="$(curl -sS -X POST -H "$AUTHZ_HEADER" \
  -F "file=@backend/tests/fixtures/test_questionnaire.xlsx" \
  -F "answers_json=$(cat /tmp/answers.json)" \
  -F "org_id=$ORG_ID" \
  -F "run_id=$RUN_ID" \
  -D /tmp/export_h.$$ \
  -o /tmp/filled.xlsx -w "%{http_code}" \
  "$API_BASE/generate-excel")"
[ "$ex_code" = "200" ] || fail "POST /api/v1/generate-excel -> $ex_code"
ctype="$(grep -i '^content-type:' /tmp/export_h.$$ | tail -1 | tr -d '\r' | cut -d: -f2- | xargs || true)"
echo "$ctype" | grep -qi 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' || fail "export content-type not xlsx: $ctype"
verify_xlsx /tmp/filled.xlsx >/dev/null || fail "export xlsx invalid"
pass "POST /api/v1/generate-excel -> 200 + valid xlsx"

echo "ALL PASS"
