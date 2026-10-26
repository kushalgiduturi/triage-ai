#!/usr/bin/env bash
# Start TriageAI: FastAPI serves the API and the built React app on one port.
set -euo pipefail
cd "$(dirname "$0")"

# Seed on first start if the image was built without a database (e.g. a mounted volume).
python -m app.seed --if-empty

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}"
