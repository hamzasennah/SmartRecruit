#!/usr/bin/env bash
set -euo pipefail

python scripts/free_port.py 8003

vllm serve "${QWEN_EMBEDDING_MODEL:-Qwen/Qwen3-Embedding-0.6B}" \
  --host 127.0.0.1 \
  --port 8003 \
  --dtype auto \
  --gpu-memory-utilization 0.20 \
  --max-model-len 4096 \
  --max-num-seqs 8 \
  --enforce-eager
