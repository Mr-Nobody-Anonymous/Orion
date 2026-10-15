#!/usr/bin/env bash
set -euo pipefail

echo "=== Starting ORION System ==="

if [ -d ".venv" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

export PYTHONPATH="src:${PYTHONPATH:-}"

echo "Starting Orion API backend on http://127.0.0.1:8000..."
python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
