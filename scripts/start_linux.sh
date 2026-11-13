#!/usr/bin/env bash
# MARS SURVIVE 360 - start the web app on a free port
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
[ -f .venv/bin/activate ] && . .venv/bin/activate
PORT=$(python3 scripts/find_port.py 8501)
echo "MARS SURVIVE 360 -> http://localhost:${PORT}"
( sleep 3; command -v xdg-open >/dev/null && xdg-open "http://localhost:${PORT}" >/dev/null 2>&1 || true ) &
exec python3 -m streamlit run app.py --server.port "$PORT" --server.headless true 2>> logs/start_errors.log
