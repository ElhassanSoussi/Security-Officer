#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND_BASE="${BACKEND_BASE:-http://127.0.0.1:8000}"
API_BASE="${API_BASE:-$BACKEND_BASE/api/v1}"
USE_RUNNING="${E2E_USE_RUNNING:-0}"
SUPABASE_URL="$(python3 - <<'PY'
from pathlib import Path
vals={}
for raw in Path("frontend/.env.local").read_text().splitlines():
    s=raw.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k,v=s.split("=",1)
    vals[k.strip()]=v.strip()
print(vals.get("NEXT_PUBLIC_SUPABASE_URL",""))
PY
)"
SUPABASE_ANON_KEY="$(python3 - <<'PY'
from pathlib import Path
vals={}
for raw in Path("frontend/.env.local").read_text().splitlines():
    s=raw.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k,v=s.split("=",1)
    vals[k.strip()]=v.strip()
print(vals.get("NEXT_PUBLIC_SUPABASE_ANON_KEY",""))
PY
)"

if [ -z "${SUPABASE_URL}" ] || [ -z "${SUPABASE_ANON_KEY}" ]; then
  echo "Supabase env missing; populate frontend/.env.local" >&2
  exit 1
fi

if [ -f ".smoke.env" ]; then
  # shellcheck disable=SC1091
  set -a; source ".smoke.env"; set +a
fi

if [ -z "${SMOKE_EMAIL:-}" ] || [ -z "${SMOKE_PASSWORD:-}" ]; then
  if [ -x "./scripts/smoke_setup.sh" ]; then
    echo "SMOKE creds missing; invoking smoke_setup..."
    ./scripts/smoke_setup.sh || true
    if [ -f ".smoke.env" ]; then set -a; source ".smoke.env"; set +a; fi
  fi
fi

[ -n "${SMOKE_EMAIL:-}" ] || { echo "SMOKE_EMAIL not set (set vars or run ./scripts/smoke_setup.sh)" >&2; exit 1; }
[ -n "${SMOKE_PASSWORD:-}" ] || { echo "SMOKE_PASSWORD not set (set vars or run ./scripts/smoke_setup.sh)" >&2; exit 1; }

cleanup() {
  if [ "$USE_RUNNING" = "1" ]; then
    return
  fi
  if [ "${E2E_KEEP_STACK:-0}" != "1" ]; then
    docker compose down >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [ "$USE_RUNNING" != "1" ] && ! docker info >/dev/null 2>&1; then
  echo "Docker daemon not available; reusing currently running local stack."
  USE_RUNNING=1
fi

if [ "$USE_RUNNING" != "1" ]; then
  echo "Starting stack with docker compose..."
  docker compose up -d --build >/dev/null
fi

wait_for() {
  local url="$1"; local label="$2"; local tries=30
  for _ in $(seq 1 $tries); do
    code=$(curl -s -o /tmp/e2e_resp.json -w "%{http_code}" "$url" || true)
    if [ "$code" = "200" ]; then
      return 0
    fi
    sleep 2
  done
  echo "FAIL: $label not ready (last code=$code)" >&2
  exit 1
}

wait_for "$BACKEND_BASE/health" "backend /health"
wait_for "$API_BASE/ready" "backend /ready"

echo "Health checks passed."

AUTH_JSON="$(curl -sS -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$SMOKE_EMAIL\",\"password\":\"$SMOKE_PASSWORD\"}")"
TOKEN="$(AUTH_JSON="$AUTH_JSON" python3 - <<'PY'
import json
import os

raw = os.environ.get("AUTH_JSON", "")
try:
    obj = json.loads(raw) if raw else {}
except json.JSONDecodeError:
    obj = {}
print(obj.get("access_token") or "")
PY
)"

[ -n "$TOKEN" ] || { echo "Login failed; check SMOKE_EMAIL/SMOKE_PASSWORD" >&2; exit 1; }
AUTHZ="Authorization: Bearer $TOKEN"

org_code=$(curl -sS -H "$AUTHZ" -o /tmp/e2e_org.json -w "%{http_code}" "$API_BASE/orgs/current")
if [ "$org_code" = "404" ]; then
  org_code=$(curl -sS -X POST -H "$AUTHZ" -o /tmp/e2e_org.json -w "%{http_code}" "$API_BASE/orgs/onboard")
fi
[ "$org_code" = "200" ] || { echo "Org bootstrap failed ($org_code)" >&2; exit 1; }
ORG_ID=$(python3 - <<'PY'
import json
obj=json.load(open("/tmp/e2e_org.json"))
print(obj.get("id") or "")
PY
)
[ -n "$ORG_ID" ] || { echo "Org ID missing" >&2; exit 1; }

PROJECT_NAME="e2e-$(date +%s)"
proj_code=$(curl -sS -H "$AUTHZ" -H "Content-Type: application/json" \
  -o /tmp/e2e_proj.json -w "%{http_code}" \
  -d "{\"org_id\":\"$ORG_ID\",\"name\":\"$PROJECT_NAME\"}" \
  "$API_BASE/projects")
[ "$proj_code" = "200" ] || { echo "Project create failed ($proj_code)" >&2; exit 1; }

curl -sS -o /tmp/e2e_sample.xlsx "$API_BASE/runs/samples/questionnaire"
[ -s /tmp/e2e_sample.xlsx ] || { echo "Sample questionnaire download failed (empty file)" >&2; exit 1; }

an_code=$(curl -sS -X POST -H "$AUTHZ" \
  -F "file=@/tmp/e2e_sample.xlsx" \
  -F "org_id=$ORG_ID" \
  -o /tmp/e2e_analyze.json -w "%{http_code}" \
  "$API_BASE/analyze-excel")
[ "$an_code" = "200" ] || { echo "Analyze failed ($an_code)" >&2; exit 1; }

RUN_ID=$(python3 - <<'PY'
import json
obj=json.load(open("/tmp/e2e_analyze.json"))
print(obj.get("run_id") or "")
PY
)
[ -n "$RUN_ID" ] || { echo "run_id missing" >&2; exit 1; }

python3 - <<'PY'
import json
src=json.load(open("/tmp/e2e_analyze.json"))
items=src.get("data") or []
out=[]
for it in items:
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
open("/tmp/e2e_answers.json","w").write(json.dumps(out,separators=(',',':')))
PY

ex_code=$(curl -sS -X POST -H "$AUTHZ" \
  -F "file=@/tmp/e2e_sample.xlsx" \
  -F "answers_json=$(cat /tmp/e2e_answers.json)" \
  -F "org_id=$ORG_ID" \
  -F "run_id=$RUN_ID" \
  -D /tmp/e2e_export_h.txt \
  -o /tmp/e2e_export.xlsx -w "%{http_code}" \
  "$API_BASE/generate-excel")
[ "$ex_code" = "200" ] || { echo "Export failed ($ex_code)" >&2; exit 1; }

dl_code=$(curl -sS -H "$AUTHZ" -D /tmp/e2e_dl_h.txt -o /tmp/e2e_dl.xlsx -w "%{http_code}" "$API_BASE/runs/$RUN_ID/download")
[ "$dl_code" = "200" ] || { echo "Download failed ($dl_code)" >&2; exit 1; }
[ -s /tmp/e2e_dl.xlsx ] || { echo "Download failed (empty file)" >&2; exit 1; }

python3 - <<'PY'
import zipfile,sys
for p in ["/tmp/e2e_export.xlsx","/tmp/e2e_dl.xlsx"]:
    with zipfile.ZipFile(p) as z:
        assert "[Content_Types].xml" in z.namelist()
print("E2E PASS")
PY
