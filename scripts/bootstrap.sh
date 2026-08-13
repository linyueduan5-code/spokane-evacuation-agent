#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/danny/Documents/救灾"
BUNDLED_PYTHON="/Users/danny/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"

if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.12)"
elif [[ -x "$BUNDLED_PYTHON" ]]; then
  PYTHON_BIN="$BUNDLED_PYTHON"
else
  PYTHON_BIN="$(command -v python3)"
fi

cd "$PROJECT_DIR"
"$PYTHON_BIN" -m venv .venv-runtime
.venv-runtime/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend install

echo "Dependencies installed. Run ./scripts/run.sh"

