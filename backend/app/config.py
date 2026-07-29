from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent


def load_backend_env(path: Path = BACKEND_ROOT / ".env") -> None:
    # utf-8-sig accepts .env files saved by Windows editors with a BOM.
    load_dotenv(path, encoding="utf-8-sig")


load_backend_env()


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
        "http://localhost:5174",
        "http://127.0.0.1:5174",
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
    def llm_seed(self) -> int | None:
        value = os.getenv("NVIDIA_SEED", "0").strip()
        return int(value) if value else None

    @property
    def embedding_dimensions(self) -> int | None:
        value = os.getenv("NVIDIA_EMBEDDING_DIMENSIONS", "").strip()
        # Empty dimensions means "use the model-native vector size".
        return int(value) if value else None

    @property
    def database_url(self) -> str:
        return os.getenv("DATABASE_URL", "").strip()

    @property
    def max_upload_mb(self) -> int:
        return int(os.getenv("MAX_UPLOAD_MB", "20"))

    @property
    def max_upload_bytes(self) -> int:
        value = os.getenv("MAX_UPLOAD_BYTES", "").strip()
        return int(value) if value else self.max_upload_mb * 1024 * 1024

    @property
    def max_total_upload_mb(self) -> int:
        return int(os.getenv("MAX_TOTAL_UPLOAD_MB", "100"))

    @property
    def max_total_upload_bytes(self) -> int:
        value = os.getenv("MAX_TOTAL_UPLOAD_BYTES", "").strip()
        return int(value) if value else self.max_total_upload_mb * 1024 * 1024

    @property
    def max_cv_files(self) -> int:
        return int(os.getenv("MAX_CV_FILES", "20"))

    @property
    def upload_chunk_bytes(self) -> int:
        return int(os.getenv("UPLOAD_CHUNK_BYTES", str(1024 * 1024)))

    @property
    def smartrecruit_api_key(self) -> str:
        return os.getenv("SMARTRECRUIT_API_KEY", "").strip()

    @property
    def rate_limit_requests(self) -> int:
        return int(os.getenv("RATE_LIMIT_REQUESTS", "20"))

    @property
    def rate_limit_window_seconds(self) -> int:
        return int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

    @property
    def job_worker_count(self) -> int:
        return int(os.getenv("JOB_WORKER_COUNT", "2"))

    @property
    def embedding_batch_size(self) -> int:
        return int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

    @property
    def llm_input_char_limit(self) -> int:
        return int(os.getenv("LLM_INPUT_CHAR_LIMIT", "12000"))

    @property
    def vector_backend(self) -> str:
        # pgvector is the default for production-style search, while json keeps
        # local/test environments usable without the extension.
        return os.getenv("VECTOR_BACKEND", "pgvector").strip().lower()

    @property
    def model_audit_log_path(self) -> str:
        return os.getenv("MODEL_AUDIT_LOG_PATH", "").strip()


settings = Settings()

# Role dans le projet:
# Ce fichier centralise les parametres runtime lus depuis l'environnement. Les clients, routes et services l'utilisent pour eviter des constantes dispersees.
