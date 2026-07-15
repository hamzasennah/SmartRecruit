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
    def llm_base_url(self) -> str:
        return os.getenv("QWEN_BASE_URL", "http://localhost:11434/v1").strip().rstrip("/")

    @property
    def llm_model(self) -> str:
        return os.getenv("QWEN_LLM_MODEL", "qwen2.5:7b").strip()

    @property
    def embedding_base_url(self) -> str:
        return os.getenv("QWEN_EMBEDDING_BASE_URL", self.llm_base_url).strip().rstrip("/")

    @property
    def embedding_model(self) -> str:
        return os.getenv("QWEN_EMBEDDING_MODEL", "qwen3-embedding:0.6b").strip()

    @property
    def database_url(self) -> str:
        return os.getenv("DATABASE_URL", "").strip()

    @property
    def max_upload_mb(self) -> int:
        return int(os.getenv("MAX_UPLOAD_MB", "20"))


settings = Settings()
