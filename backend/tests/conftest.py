import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("NVIDIA_API_KEY", "nvapi-test-key-000000000000000000000000")
os.environ.setdefault("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
os.environ.setdefault("NVIDIA_LLM_MODEL", "meta/llama-3.1-8b-instruct")
os.environ.setdefault("NVIDIA_EMBEDDING_BASE_URL", "https://integrate.api.nvidia.com/v1")
os.environ.setdefault("NVIDIA_EMBEDDING_MODEL", "nvidia/llama-nemotron-embed-1b-v2")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://smartrecruit:change_me@localhost:5432/smartrecruit")
os.environ.setdefault("SMARTRECRUIT_API_KEY", "ci-test-key")
os.environ.setdefault("VECTOR_BACKEND", "json")
