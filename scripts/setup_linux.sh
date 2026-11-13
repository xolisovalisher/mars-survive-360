#!/usr/bin/env bash
# MARS SURVIVE 360 - one-time setup on Linux/macOS
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
PY=${PYTHON:-python3}
$PY -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,13), sys.version" || { echo "[ERROR] Python 3.10-3.13 required"; exit 1; }
[ -d .venv ] || $PY -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip >> logs/setup.log 2>&1
python -m pip install -r requirements.txt 2>&1 | tee -a logs/setup.log | tail -3
[ -f .env ] || cp .env.example .env
read -r -p "Install optional ML/GIS packages (PyTorch CPU ~250 MB, GeoPandas)? [y/N] " OPT || OPT=n
if [ "${OPT,,}" = "y" ]; then
  python -m pip install torch --index-url https://download.pytorch.org/whl/cpu >> logs/setup.log 2>&1 || echo "[WARN] PyTorch not installed (sklearn MLP fallback)"
  python -m pip install geopandas >> logs/setup.log 2>&1 || echo "[WARN] GeoPandas not installed (GIS export disabled)"
fi
python scripts/check_system.py
echo "Start with: scripts/start_linux.sh"
