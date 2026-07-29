#!/usr/bin/env bash
set -euo pipefail

python scripts/free_port.py --yes --allowed-name python --allowed-name uvicorn 8002

python -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8002

# Role dans le projet:
# Ce script lance le backend en developpement. Il rassemble les etapes shell necessaires pour demarrer FastAPI localement.
