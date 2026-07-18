from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent

load_dotenv(BACKEND_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str = "SmartRecruit Backend"
    api_prefix: str = "/api"
    backend_root: Path = BACKEND_ROOT
    project_root: Path = PROJECT_ROOT
    upload_dir: Path = BACKEND_ROOT / "uploads"
    storage_dir: Path = BACKEND_ROOT / "storage"
    document_storage_dir: Path = storage_dir / "documents"
    result_storage_dir: Path = storage_dir / "results"
    data_dir: Path = BACKEND_ROOT / "app" / "data"
    allowed_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )

    @property
    def nvidia_api_key(self) -> str:
        return os.getenv("NVIDIA_API_KEY", "").strip()

    @property
    def nvidia_base_url(self) -> str:
        return os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").strip().rstrip("/")

    @property
    def llm_model(self) -> str:
        return os.getenv("NVIDIA_LLM_MODEL", "meta/llama-3.1-8b-instruct").strip()

    @property
    def embedding_base_url(self) -> str:
        return os.getenv("NVIDIA_EMBEDDING_BASE_URL", self.nvidia_base_url).strip().rstrip("/")

    @property
    def embedding_model(self) -> str:
        return os.getenv("NVIDIA_EMBEDDING_MODEL", "nvidia/llama-nemotron-embed-1b-v2").strip()

    @property
    def llm_timeout(self) -> float:
        return float(os.getenv("NVIDIA_TIMEOUT", "120"))

    @property
    def llm_max_retries(self) -> int:
        return int(os.getenv("NVIDIA_MAX_RETRIES", "2"))

    @property
    def llm_retry_delay(self) -> float:
        return float(os.getenv("NVIDIA_RETRY_DELAY", "2"))

    @property
    def llm_max_tokens(self) -> int:
        return int(os.getenv("NVIDIA_MAX_TOKENS", "8192"))

    @property
    def llm_temperature(self) -> float:
        return float(os.getenv("NVIDIA_TEMPERATURE", "0.1"))

    @property
    def embedding_dimensions(self) -> int | None:
        value = os.getenv("NVIDIA_EMBEDDING_DIMENSIONS", "").strip()
        return int(value) if value else None

    @property
    def database_url(self) -> str:
        return os.getenv("DATABASE_URL", "").strip()

    @property
    def max_upload_mb(self) -> int:
        return int(os.getenv("MAX_UPLOAD_MB", "20"))


settings = Settings()
