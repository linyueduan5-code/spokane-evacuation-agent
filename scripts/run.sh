#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/danny/Documents/救灾"

if [[ -f "$PROJECT_DIR/.env" ]]; then
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi

if [[ ! -x "$PROJECT_DIR/.venv-runtime/bin/python" ]] || [[ ! -d "$PROJECT_DIR/frontend/node_modules" ]]; then
  echo "Dependencies are missing. Run ./scripts/bootstrap.sh first."
  exit 1
fi

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$PROJECT_DIR/backend"
../.venv-runtime/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

cd "$PROJECT_DIR/frontend"
npm run dev -- --host 127.0.0.1 &
FRONTEND_PID=$!

echo "EMBER running at http://127.0.0.1:5173"
echo "FastAPI docs at http://127.0.0.1:8000/docs"
wait
