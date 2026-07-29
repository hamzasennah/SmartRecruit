from __future__ import annotations

import json
import logging
import time
from typing import Any, ClassVar

import httpx

from app.core.exceptions import ExternalServiceError
from app.core.model_audit import provider_request_id, record_model_call, utc_now_iso


class NvidiaAPIClient:
    call_type: ClassVar[str]
    missing_api_key_message: ClassVar[str]
    retry_log_label: ClassVar[str]
    unavailable_error_prefix: ClassVar[str]

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        max_retries: int,
        retry_delay: float,
        logger: logging.Logger,
    ) -> None:
        if not api_key:
            raise ExternalServiceError(self.missing_api_key_message)
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._logger = logger

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            started_at = utc_now_iso()
            started_perf = time.perf_counter()
            response: httpx.Response | None = None
            try:
                response = httpx.post(url, headers=self.headers, json=payload, timeout=self.timeout)
                latency_ms = (time.perf_counter() - started_perf) * 1000
                record_model_call(
                    provider="nvidia",
                    call_type=self.call_type,
                    method="POST",
                    url=url,
                    endpoint=path,
                    model=str(payload.get("model", self.model)),
                    started_at=started_at,
                    latency_ms=latency_ms,
                    attempt=attempt,
                    max_attempts=self.max_retries + 1,
                    status_code=response.status_code,
                    provider_request_id_value=provider_request_id(response.headers),
                    success=200 <= response.status_code < 400,
                    input_summary=self._input_summary(payload),
                )
                # Retry only transient provider/server statuses; other HTTP
                # errors surface immediately through raise_for_status.
                if response.status_code in {429, 500, 502, 503, 504} and attempt <= self.max_retries:
                    self._logger.warning(
                        "%s tentative %s/%s echouee avec HTTP %s.",
                        self.retry_log_label,
                        attempt,
                        self.max_retries + 1,
                        response.status_code,
                    )
                    time.sleep(self.retry_delay)
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                if response is None:
                    # If no response object exists, we still write an audit event
                    # so network failures are visible in the same log stream.
                    latency_ms = (time.perf_counter() - started_perf) * 1000
                    record_model_call(
                        provider="nvidia",
                        call_type=self.call_type,
                        method="POST",
                        url=url,
                        endpoint=path,
                        model=str(payload.get("model", self.model)),
                        started_at=started_at,
                        latency_ms=latency_ms,
                        attempt=attempt,
                        max_attempts=self.max_retries + 1,
                        success=False,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        input_summary=self._input_summary(payload),
                    )
                last_error = exc
                if attempt <= self.max_retries:
                    self._logger.warning(
                        "%s tentative %s/%s echouee: %s",
                        self.retry_log_label,
                        attempt,
                        self.max_retries + 1,
                        exc,
                    )
                    time.sleep(self.retry_delay)
                    continue
                break
        raise ExternalServiceError(f"{self.unavailable_error_prefix}: {last_error}") from last_error

    def _input_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {}

# Role dans le projet:
# Ce fichier factorise le transport HTTP NVIDIA. Les clients LLM et embeddings heritent de ses retries, headers et evenements d'audit.
