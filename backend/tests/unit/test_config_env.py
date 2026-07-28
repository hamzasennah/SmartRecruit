import json
import os

import pytest
from app.config import load_backend_env, settings
from app.core.config_validation import ConfigValidationError, validate_startup_settings
from app.core.model_audit import record_model_call
from app.infrastructure.nvidia_embeddings import NvidiaEmbeddingClient


def test_load_backend_env_accepts_utf8_bom(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("\ufeffNVIDIA_API_KEY=test-key\n", encoding="utf-8")
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    load_backend_env(env_file)

    assert os.getenv("NVIDIA_API_KEY") == "test-key"


def test_llm_temperature_defaults_to_low_variability_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_TEMPERATURE", raising=False)

    assert settings.llm_temperature == 0.1


def test_model_audit_log_path_writes_jsonl_event(tmp_path, monkeypatch) -> None:
    audit_path = tmp_path / "logs" / "model_audit.jsonl"
    monkeypatch.setenv("MODEL_AUDIT_LOG_PATH", str(audit_path))

    event = record_model_call(
        provider="nvidia",
        call_type="llm",
        method="POST",
        url="https://integrate.api.nvidia.com/v1/chat/completions",
        endpoint="/chat/completions",
        model="meta/llama-3.1-8b-instruct",
        started_at="2026-07-27T00:00:00.000+00:00",
        latency_ms=12.3456,
        attempt=1,
        max_attempts=1,
        status_code=200,
        success=True,
        input_summary={"prompt_chars": 42},
    )

    assert audit_path.exists()
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    logged_event = json.loads(lines[0])
    assert logged_event["audit_call_id"] == event["audit_call_id"]
    assert logged_event["provider"] == "nvidia"
    assert logged_event["model"] == "meta/llama-3.1-8b-instruct"
    assert logged_event["success"] is True


def test_empty_upload_byte_overrides_fall_back_to_megabyte_limits(monkeypatch) -> None:
    monkeypatch.setenv("MAX_UPLOAD_MB", "7")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "")
    monkeypatch.setenv("MAX_TOTAL_UPLOAD_MB", "13")
    monkeypatch.setenv("MAX_TOTAL_UPLOAD_BYTES", "")

    assert settings.max_upload_bytes == 7 * 1024 * 1024
    assert settings.max_total_upload_bytes == 13 * 1024 * 1024


def test_empty_embedding_dimensions_uses_model_native_dimension() -> None:
    client = CapturingEmbeddingClient(dimensions=None)

    assert client.embed_query("ping") == [0.1, 0.2, 0.3]
    assert client.payload is not None
    assert "dimensions" not in client.payload


def test_config_validation_rejects_invalid_nvidia_api_key(monkeypatch) -> None:
    _set_valid_startup_env(monkeypatch)
    monkeypatch.setenv("NVIDIA_API_KEY", "your_nvidia_api_key_here")

    with pytest.raises(ConfigValidationError, match="NVIDIA_API_KEY"):
        validate_startup_settings(settings)


def test_config_validation_accepts_current_shape_with_empty_optional_overrides(monkeypatch) -> None:
    _set_valid_startup_env(monkeypatch)
    monkeypatch.setenv("NVIDIA_EMBEDDING_DIMENSIONS", "")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "")
    monkeypatch.setenv("MAX_TOTAL_UPLOAD_BYTES", "")

    validate_startup_settings(settings)


class CapturingEmbeddingClient(NvidiaEmbeddingClient):
    def __init__(self, dimensions: int | None) -> None:
        super().__init__(
            api_key="nvapi-test-key-000000000000000000000000",
            base_url="https://example.test/v1",
            model="embedding-model",
            timeout=10,
            max_retries=0,
            retry_delay=0,
            dimensions=dimensions,
        )
        self.payload = None

    def _post(self, path: str, payload: dict) -> dict:
        self.payload = payload
        return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}


def _set_valid_startup_env(monkeypatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key-000000000000000000000000")
    monkeypatch.setenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("NVIDIA_LLM_MODEL", "meta/llama-3.1-8b-instruct")
    monkeypatch.setenv("NVIDIA_EMBEDDING_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("NVIDIA_EMBEDDING_MODEL", "nvidia/llama-nemotron-embed-1b-v2")
    monkeypatch.setenv("NVIDIA_TIMEOUT", "120")
    monkeypatch.setenv("NVIDIA_MAX_RETRIES", "2")
    monkeypatch.setenv("NVIDIA_RETRY_DELAY", "2")
    monkeypatch.setenv("NVIDIA_MAX_TOKENS", "8192")
    monkeypatch.setenv("NVIDIA_TEMPERATURE", "0.1")
    monkeypatch.setenv("NVIDIA_SEED", "0")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://smartrecruit:change_me@localhost:5432/smartrecruit")
    monkeypatch.setenv("MAX_UPLOAD_MB", "20")
    monkeypatch.setenv("MAX_TOTAL_UPLOAD_MB", "100")
    monkeypatch.setenv("MAX_CV_FILES", "20")
    monkeypatch.setenv("UPLOAD_CHUNK_BYTES", "1048576")
    monkeypatch.setenv("SMARTRECRUIT_API_KEY", "local-development-key")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "20")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("JOB_WORKER_COUNT", "2")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "32")
    monkeypatch.setenv("LLM_INPUT_CHAR_LIMIT", "12000")
    monkeypatch.setenv("VECTOR_BACKEND", "json")
