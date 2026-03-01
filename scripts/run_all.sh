#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Preflight checks (env files, URL format). No secrets printed.
if [ -x "$ROOT/scripts/doctor.sh" ]; then
  echo ""
  "$ROOT/scripts/doctor.sh"
  echo ""
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found. Install Docker Desktop or Colima."
  exit 1
fi

# Ensure the daemon is reachable (Docker Desktop or Colima must be running).
if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running or not reachable."
  echo "Start Docker Desktop, or if you use Colima: colima start"
  exit 1
fi

# Load local env files (gitignored) so docker build args have the right values.
# We intentionally do not echo any secret values.
if [ -f "backend/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "backend/.env"
  set +a
fi
if [ -f "frontend/.env.local" ]; then
  set -a
  # shellcheck disable=SC1091
  source "frontend/.env.local"
  set +a
fi

# Ensure docker-compose.yml substitutions for the frontend build are present.
: "${NEXT_PUBLIC_SUPABASE_URL:=${SUPABASE_URL:-}}"
: "${NEXT_PUBLIC_SUPABASE_ANON_KEY:=${SUPABASE_KEY:-}}"
export NEXT_PUBLIC_SUPABASE_URL NEXT_PUBLIC_SUPABASE_ANON_KEY

COMPOSE="docker compose"
$COMPOSE version >/dev/null 2>&1 || COMPOSE="docker-compose"

echo "Starting stack (backend:8000, frontend:3001)..."
$COMPOSE up --build -d

echo "Waiting for backend..."
for i in {1..60}; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "Backend is up."
    break
  fi
  sleep 1
  if [ "$i" -eq 60 ]; then
    echo "Backend did not become healthy."
    $COMPOSE logs --tail=80 backend || true
    exit 1
  fi
done

echo "Waiting for frontend..."
for i in {1..60}; do
  if curl -fsS http://127.0.0.1:3001 >/dev/null 2>&1; then
    echo "Frontend is up."
    break
  fi
  sleep 1
  if [ "$i" -eq 60 ]; then
    echo "Frontend did not become healthy."
    $COMPOSE logs --tail=80 frontend || true
    exit 1
  fi
done

echo ""
echo "Stack is ready."
echo "Frontend: http://localhost:3001"
echo "Backend : http://localhost:8000/health"
echo ""
echo "To stop: $COMPOSE down"
