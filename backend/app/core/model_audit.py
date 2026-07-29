from __future__ import annotations

import json
import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.config import settings
from app.core.request_context import get_analysis_id, get_request_id

logger = logging.getLogger(__name__)

_model_call_context: ContextVar[dict[str, str] | None] = ContextVar("model_call_context", default=None)
_audit_lock = threading.Lock()

_REQUEST_ID_HEADERS = (
    "x-request-id",
    "x-correlation-id",
    "x-nvidia-request-id",
    "x-nv-request-id",
    "nvcf-reqid",
    "nvcf-request-id",
)


@contextmanager
def model_call_context(**values: object) -> Iterator[None]:
    current = dict(_model_call_context.get() or {})
    for key, value in values.items():
        if value is not None:
            current[key] = str(value)
    token = _model_call_context.set(current)
    try:
        yield
    finally:
        _model_call_context.reset(token)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def provider_request_id(headers) -> str | None:
    for header in _REQUEST_ID_HEADERS:
        value = headers.get(header)
        if value:
            return str(value)
    return None


def record_model_call(
    *,
    provider: str,
    call_type: str,
    method: str,
    url: str,
    endpoint: str,
    model: str,
    started_at: str,
    latency_ms: float,
    attempt: int,
    max_attempts: int,
    status_code: int | None = None,
    provider_request_id_value: str | None = None,
    success: bool = False,
    error_type: str | None = None,
    error_message: str | None = None,
    input_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    # Audit events are intentionally metadata-only: they identify the model,
    # endpoint, attempts, and context without storing full prompts or CV content.
    event: dict[str, object] = {
        "audit_call_id": uuid4().hex,
        "analysis_id": get_analysis_id(),
        "request_id": get_request_id(),
        "timestamp": utc_now_iso(),
        "started_at": started_at,
        "latency_ms": round(latency_ms, 3),
        "provider": provider,
        "call_type": call_type,
        "method": method,
        "url": url,
        "endpoint": endpoint,
        "model": model,
        "attempt": attempt,
        "max_attempts": max_attempts,
        "status_code": status_code,
        "provider_request_id": provider_request_id_value,
        "success": success,
        "context": dict(_model_call_context.get() or {}),
    }
    if input_summary:
        event["input_summary"] = input_summary
    if error_type:
        event["error_type"] = error_type
    if error_message:
        event["error_message"] = error_message[:500]

    _write_audit_event(event)
    logger.info(
        "Appel modele audite.",
        extra={
            "analysis_id": event["analysis_id"],
            "model": model,
            "endpoint": endpoint,
            "status_code": status_code,
            "latency_ms": event["latency_ms"],
        },
    )
    return event


def _write_audit_event(event: dict[str, object]) -> None:
    raw_path = settings.model_audit_log_path
    if not raw_path:
        return
    path = Path(raw_path)
    if not path.is_absolute():
        path = settings.backend_root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, sort_keys=True)
    with _audit_lock:
        # A process-level lock prevents interleaved JSONL writes when concurrent
        # analysis jobs call the model at the same time.
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

# Role dans le projet:
# Ce fichier audite les appels modele. Les clients NVIDIA l'appellent pour relier latence, endpoint, modele et contexte d'analyse.
