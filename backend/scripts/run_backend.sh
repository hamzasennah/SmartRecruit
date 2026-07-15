#!/usr/bin/env bash
set -euo pipefail

python scripts/free_port.py 8002

python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8002
