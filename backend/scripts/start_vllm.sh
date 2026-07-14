#!/usr/bin/env bash
set -euo pipefail

python -m vllm.entrypoints.openai.api_server \
  --model "${QWEN_LLM_MODEL:-Qwen/Qwen2.5-7B-Instruct}" \
  --host 0.0.0.0 \
  --port 8000

