#!/usr/bin/env bash
set -euo pipefail

# Start the FastAPI backend locally (port 8000).
# Secrets must come from environment variables or backend/.env (gitignored).

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Load backend/.env if present (do not echo values).
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

# Prefer .venv, fall back to venv, then system python3
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
elif [ -x "$ROOT/venv/bin/python" ]; then
  PY="$ROOT/venv/bin/python"
else
  PY="python3"
fi

exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

