#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

red() { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }

fail=0

need_file() {
  local path="$1"
  local hint="$2"
  if [ ! -f "$path" ]; then
    red "Missing: $path"
    echo "  $hint"
    fail=1
  else
    green "OK: $path"
  fi
}

echo "Doctor: NYC Compliance Architect"
echo "--------------------------------"

need_file "frontend/.env.local" "Create it from frontend/.env.local.example"
need_file "backend/.env" "Create it from backend/.env.example"
need_file ".env" "Create it from .env.example (used by docker compose builds)"

if [ "$fail" -ne 0 ]; then
  echo ""
  red "Fix the missing files above, then re-run: ./scripts/doctor.sh"
  exit 1
fi

python3 - <<'PY'
from __future__ import annotations
from pathlib import Path
from urllib.parse import urlparse
import base64
import json
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[0]

def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out

def b64url_decode(data: str) -> bytes:
    # Add padding for base64url
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("utf-8"))

def describe_key(key: str) -> str:
    k = (key or "").strip()
    if not k:
        return "MISSING"
    if k.startswith("sb_secret_"):
        return "sb_secret_* (server-only)"
    if k.startswith("sb_publishable_"):
        return "sb_publishable_*"
    if k.startswith("eyJ"):
        parts = k.split(".")
        if len(parts) >= 2:
            try:
                payload = json.loads(b64url_decode(parts[1]).decode("utf-8", "replace"))
                role = payload.get("role") or payload.get("aud") or "unknown"
                return f"jwt role={role!r}"
            except Exception:
                return "jwt (unparsed)"
        return "jwt (invalid)"
    return f"unknown format (prefix={k[:6]!r})"

def check_url(name: str, value: str) -> tuple[bool, str]:
    v = (value or "").strip()
    if not v:
        return False, "MISSING"
    try:
        u = urlparse(v)
        host = u.hostname or ""
        if u.scheme not in ("http", "https") or not host:
            return False, f"Invalid URL ({v})"
        if not host.endswith(".supabase.co"):
            return True, f"OK host={host} (note: expected *.supabase.co)"
        return True, f"OK host={host}"
    except Exception:
        return False, f"Invalid URL ({v})"

def require(env: dict[str, str], key: str) -> str:
    v = (env.get(key) or "").strip()
    if not v:
        raise KeyError(key)
    return v

errors: list[str] = []

fe = load_env(ROOT / "frontend/.env.local")
be = load_env(ROOT / "backend/.env")
root = load_env(ROOT / ".env")

def ok(msg: str):
    print(f"OK: {msg}")

def warn(msg: str):
    print(f"WARN: {msg}")

def bad(msg: str):
    errors.append(msg)
    print(f"ERROR: {msg}")

# Frontend
try:
    url = require(fe, "NEXT_PUBLIC_SUPABASE_URL")
    good, detail = check_url("NEXT_PUBLIC_SUPABASE_URL", url)
    (ok if good else bad)(f"frontend NEXT_PUBLIC_SUPABASE_URL -> {detail}")
except KeyError:
    bad("frontend missing NEXT_PUBLIC_SUPABASE_URL")

try:
    anon = require(fe, "NEXT_PUBLIC_SUPABASE_ANON_KEY")
    ok(f"frontend NEXT_PUBLIC_SUPABASE_ANON_KEY -> {describe_key(anon)}")
    if anon.strip().startswith("sb_secret_"):
        bad("frontend uses sb_secret_* key; use anon/public or sb_publishable_* instead")
except KeyError:
    bad("frontend missing NEXT_PUBLIC_SUPABASE_ANON_KEY")

# Backend
try:
    url = require(be, "SUPABASE_URL")
    good, detail = check_url("SUPABASE_URL", url)
    (ok if good else bad)(f"backend SUPABASE_URL -> {detail}")
except KeyError:
    bad("backend missing SUPABASE_URL")

try:
    key = require(be, "SUPABASE_KEY")
    ok(f"backend SUPABASE_KEY -> {describe_key(key)}")
except KeyError:
    bad("backend missing SUPABASE_KEY")

secret_key = (be.get("SUPABASE_SECRET_KEY") or "").strip()
svc = (be.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
if secret_key:
    ok(f"backend SUPABASE_SECRET_KEY -> {describe_key(secret_key)}")
if svc:
    ok(f"backend SUPABASE_SERVICE_ROLE_KEY -> {describe_key(svc)}")
if not secret_key and not svc:
    warn("backend missing SUPABASE_SECRET_KEY / SUPABASE_SERVICE_ROLE_KEY (admin automation like smoke_setup may fail)")

jwt_secret = (be.get("SUPABASE_JWT_SECRET") or "").strip()
if jwt_secret:
    ok("backend SUPABASE_JWT_SECRET -> present")
else:
    warn("backend SUPABASE_JWT_SECRET is empty (backend will validate via Supabase auth fallback)")

# Docker compose substitution
try:
    url = require(root, "NEXT_PUBLIC_SUPABASE_URL")
    good, detail = check_url("NEXT_PUBLIC_SUPABASE_URL", url)
    (ok if good else bad)(f"docker .env NEXT_PUBLIC_SUPABASE_URL -> {detail}")
except KeyError:
    bad("docker .env missing NEXT_PUBLIC_SUPABASE_URL")

try:
    anon = require(root, "NEXT_PUBLIC_SUPABASE_ANON_KEY")
    ok(f"docker .env NEXT_PUBLIC_SUPABASE_ANON_KEY -> {describe_key(anon)}")
    if anon.strip().startswith("sb_secret_"):
        bad("docker .env uses sb_secret_* key; use anon/public or sb_publishable_* instead")
except KeyError:
    bad("docker .env missing NEXT_PUBLIC_SUPABASE_ANON_KEY")

print("")
if errors:
    print("Doctor result: FAIL")
    for e in errors:
        print(f" - {e}")
    sys.exit(1)
print("Doctor result: OK")
PY

echo ""
green "Next steps:"
echo "  - Local dev: ./scripts/start_all.sh --restart"
echo "  - Docker:    ./scripts/run_all.sh   (Docker Desktop or Colima must be running)"
