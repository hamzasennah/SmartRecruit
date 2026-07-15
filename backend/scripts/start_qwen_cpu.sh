#!/usr/bin/env bash
set -euo pipefail

python scripts/free_port.py 11434

ollama serve
