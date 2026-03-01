#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RESTART_MODE=false
if [ "${1:-}" = "--restart" ]; then
    RESTART_MODE=true
fi

check_port_free() {
    local port="$1"
    local name="$2"
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
        if [ "$RESTART_MODE" = true ]; then
            echo "ℹ️ Port $port is in use; stopping existing listener (--restart mode)."
            local pids
            pids="$(lsof -t -nP -iTCP:"$port" -sTCP:LISTEN | tr '\n' ' ')"
            if [ -n "$pids" ]; then
                kill $pids 2>/dev/null || true
                sleep 1
            fi
            if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
                echo "❌ Could not free port $port automatically."
                lsof -nP -iTCP:"$port" -sTCP:LISTEN
                exit 1
            fi
            return
        fi
        echo "❌ Port $port is already in use ($name)."
        echo "   Stop the existing process first, then re-run ./scripts/start_all.sh"
        echo "   Or run: ./scripts/start_all.sh --restart"
        lsof -nP -iTCP:"$port" -sTCP:LISTEN
        exit 1
    fi
}

# Function to kill background processes on exit
cleanup() {
    echo ""
    echo "🛑 Stopping all services..."
    pids="$(jobs -p || true)"
    if [ -n "$pids" ]; then
        kill $pids 2>/dev/null || true
    fi
    exit
}

# Trap Ctrl+C (SIGINT) and termination signal (SIGTERM)
trap cleanup SIGINT SIGTERM

echo "🚀 Starting Security Officer Application..."

# Preflight checks (env files, URL format). No secrets printed.
if [ -x "$ROOT/scripts/doctor.sh" ]; then
    echo ""
    "$ROOT/scripts/doctor.sh"
    echo ""
fi

# Preflight: avoid confusing startup errors.
check_port_free 8000 "backend"
check_port_free 3001 "frontend"

# 1. Start Backend (using the fix script)
echo "---------------------------------------------------"
echo "📦 Starting Backend (Port 8000)..."
echo "---------------------------------------------------"
"$ROOT/backend/start_backend.sh" &
BACKEND_PID=$!

# Wait a few seconds for Backend to start initializing
sleep 3
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "❌ Backend failed to start. Check backend logs above."
    exit 1
fi

# 2. Start Frontend
echo "---------------------------------------------------"
echo "🎨 Starting Frontend (Port 3001)..."
echo "---------------------------------------------------"
cd "$ROOT/frontend"

# Ensure Next.js sees public env vars at startup/build time.
if [ -f ".env.local" ]; then
    set -a
    # shellcheck disable=SC1091
    source ".env.local"
    set +a
fi

if [ -z "${NEXT_PUBLIC_SUPABASE_URL:-}" ] || [ -z "${NEXT_PUBLIC_SUPABASE_ANON_KEY:-}" ]; then
    echo "❌ Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env.local"
    exit 1
fi

npm run dev &
FRONTEND_PID=$!

sleep 2
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "❌ Frontend failed to start. Check frontend logs above."
    kill "$BACKEND_PID" 2>/dev/null || true
    exit 1
fi

# Wait for both processes to keep the script running
wait $BACKEND_PID $FRONTEND_PID
