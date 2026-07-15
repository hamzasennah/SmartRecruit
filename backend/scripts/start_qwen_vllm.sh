#!/usr/bin/env bash
set -euo pipefail

python scripts/free_port.py 8000

vllm serve "${QWEN_LLM_MODEL:-Qwen/Qwen3.5-9B}" \
  --host 127.0.0.1 \
  --port 8000 \
  --dtype auto \
  --gpu-memory-utilization 0.90 \
  --max-model-len 4096 \
  --max-num-seqs 1 \
  --enforce-eager
