from __future__ import annotations

from urllib.parse import urlparse

from app.config import Settings


class ConfigValidationError(RuntimeError):
    pass


def validate_startup_settings(settings: Settings) -> None:
    errors: list[str] = []
    _require_plausible_nvidia_key("NVIDIA_API_KEY", settings.nvidia_api_key, errors)
    _require_url("NVIDIA_BASE_URL", settings.nvidia_base_url, errors)
    _require_url("NVIDIA_EMBEDDING_BASE_URL", settings.embedding_base_url, errors)
    _require_text("NVIDIA_LLM_MODEL", settings.llm_model, errors)
    _require_text("NVIDIA_EMBEDDING_MODEL", settings.embedding_model, errors)
    _require_database_url("DATABASE_URL", settings.database_url, errors)
    _require_text("SMARTRECRUIT_API_KEY", settings.smartrecruit_api_key, errors, min_length=8)
    _require_choice("VECTOR_BACKEND", settings.vector_backend, {"pgvector", "json"}, errors)
    _require_positive("NVIDIA_TIMEOUT", settings.llm_timeout, errors)
    _require_positive_int("NVIDIA_MAX_RETRIES", settings.llm_max_retries, errors, allow_zero=True)
    _require_positive("NVIDIA_RETRY_DELAY", settings.llm_retry_delay, errors, allow_zero=True)
    _require_positive_int("NVIDIA_MAX_TOKENS", settings.llm_max_tokens, errors)
    _require_range("NVIDIA_TEMPERATURE", settings.llm_temperature, 0.0, 2.0, errors)
    if settings.llm_seed is not None and settings.llm_seed < 0:
        errors.append("NVIDIA_SEED doit etre vide ou un entier positif.")
    if settings.embedding_dimensions is not None:
        _require_positive_int("NVIDIA_EMBEDDING_DIMENSIONS", settings.embedding_dimensions, errors)
    _require_positive_int("MAX_UPLOAD_MB", settings.max_upload_mb, errors)
    _require_positive_int("MAX_UPLOAD_BYTES", settings.max_upload_bytes, errors)
    _require_positive_int("MAX_TOTAL_UPLOAD_MB", settings.max_total_upload_mb, errors)
    _require_positive_int("MAX_TOTAL_UPLOAD_BYTES", settings.max_total_upload_bytes, errors)
    if settings.max_total_upload_bytes < settings.max_upload_bytes:
        errors.append("MAX_TOTAL_UPLOAD_BYTES doit etre superieur ou egal a MAX_UPLOAD_BYTES.")
    _require_positive_int("MAX_CV_FILES", settings.max_cv_files, errors)
    _require_positive_int("UPLOAD_CHUNK_BYTES", settings.upload_chunk_bytes, errors)
    _require_positive_int("RATE_LIMIT_REQUESTS", settings.rate_limit_requests, errors)
    _require_positive_int("RATE_LIMIT_WINDOW_SECONDS", settings.rate_limit_window_seconds, errors)
    _require_positive_int("JOB_WORKER_COUNT", settings.job_worker_count, errors)
    _require_positive_int("EMBEDDING_BATCH_SIZE", settings.embedding_batch_size, errors)
    _require_positive_int("LLM_INPUT_CHAR_LIMIT", settings.llm_input_char_limit, errors)
    if errors:
        details = "; ".join(errors)
        raise ConfigValidationError(f"Configuration SmartRecruit invalide: {details}")


def _require_text(name: str, value: str, errors: list[str], *, min_length: int = 1) -> None:
    if not value or len(value.strip()) < min_length:
        errors.append(f"{name} est obligatoire et doit contenir au moins {min_length} caractere(s).")
        return
    lowered = value.strip().lower()
    if lowered in {"your_nvidia_api_key_here", "placeholder", "todo"}:
        errors.append(f"{name} contient une valeur placeholder.")


def _require_plausible_nvidia_key(name: str, value: str, errors: list[str]) -> None:
    if not value or len(value.strip()) < 24:
        errors.append(f"{name} est obligatoire et doit contenir au moins 24 caracteres.")
        return
    lowered = value.lower()
    if "your_" in lowered or "change_me" in lowered or "placeholder" in lowered:
        errors.append(f"{name} contient une valeur placeholder.")
    if not value.startswith("nvapi-"):
        errors.append(f"{name} doit commencer par 'nvapi-' pour une cle NVIDIA plausible.")


def _require_url(name: str, value: str, errors: list[str]) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append(f"{name} doit etre une URL http(s) valide.")


def _require_database_url(name: str, value: str, errors: list[str]) -> None:
    parsed = urlparse(value)
    if not parsed.scheme.startswith("postgresql") or not parsed.netloc:
        errors.append(f"{name} doit etre une URL PostgreSQL valide.")


def _require_choice(name: str, value: str, choices: set[str], errors: list[str]) -> None:
    if value not in choices:
        errors.append(f"{name} doit valoir l'une des valeurs suivantes: {', '.join(sorted(choices))}.")


def _require_positive(name: str, value: float, errors: list[str], *, allow_zero: bool = False) -> None:
    if value < 0 or (value == 0 and not allow_zero):
        comparator = "positif ou nul" if allow_zero else "strictement positif"
        errors.append(f"{name} doit etre {comparator}.")


def _require_positive_int(name: str, value: int, errors: list[str], *, allow_zero: bool = False) -> None:
    if value < 0 or (value == 0 and not allow_zero):
        comparator = "positif ou nul" if allow_zero else "strictement positif"
        errors.append(f"{name} doit etre un entier {comparator}.")


def _require_range(name: str, value: float, minimum: float, maximum: float, errors: list[str]) -> None:
    if value < minimum or value > maximum:
        errors.append(f"{name} doit etre compris entre {minimum:g} et {maximum:g}.")
