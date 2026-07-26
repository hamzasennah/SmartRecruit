from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.config import Settings
from app.core.exceptions import ExternalServiceError, OutputValidationError
from app.core.model_audit import provider_request_id, record_model_call, utc_now_iso
from app.services.extraction.output_validator import parse_json_payload

logger = logging.getLogger(__name__)


class NvidiaLLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        max_retries: int,
        retry_delay: float,
        max_tokens: int,
        temperature: float,
        seed: int | None = 0,
    ) -> None:
        if not api_key:
            raise ExternalServiceError("NVIDIA_API_KEY est obligatoire pour appeler le modele NVIDIA.")
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.seed = seed

    def generate_json(self, prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return JSON only. No markdown, no comments, no explanation. "
                        "Use null for unknown strings and [] for unknown arrays."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "top_p": 1,
            "max_tokens": self.max_tokens,
        }
        if self.seed is not None:
            payload["seed"] = self.seed
        last_error: Exception | None = None
        for parse_attempt in range(1, self.max_retries + 2):
            response = self._post("/chat/completions", payload)
            try:
                content = response["choices"][0]["message"]["content"]
                return _loads_json(content)
            except (KeyError, IndexError, TypeError) as exc:
                raise ExternalServiceError("La reponse NVIDIA LLM n'a pas le format attendu.") from exc
            except (json.JSONDecodeError, OutputValidationError) as exc:
                last_error = exc
                finish_reason = _finish_reason(response)
                preview = str(content)[-600:]
                logger.error(
                    "JSON NVIDIA invalide. tentative=%s/%s, finish_reason=%s, longueur=%s, fin_reponse=%r",
                    parse_attempt,
                    self.max_retries + 1,
                    finish_reason,
                    len(str(content)),
                    preview,
                )
                if finish_reason == "length":
                    raise ExternalServiceError(
                        "La reponse NVIDIA LLM est tronquee. Augmentez NVIDIA_MAX_TOKENS dans .env."
                    ) from exc
                if parse_attempt <= self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                break
        raise ExternalServiceError("La reponse NVIDIA LLM n'est pas un JSON exploitable.") from last_error

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            started_at = utc_now_iso()
            started_perf = time.perf_counter()
            response: httpx.Response | None = None
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=self.timeout)
                latency_ms = (time.perf_counter() - started_perf) * 1000
                record_model_call(
                    provider="nvidia",
                    call_type="llm",
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
                    input_summary={
                        "message_count": len(payload.get("messages", [])),
                        "max_tokens": payload.get("max_tokens"),
                        "temperature": payload.get("temperature"),
                        "seed": payload.get("seed"),
                    },
                )
                if response.status_code in {429, 500, 502, 503, 504} and attempt <= self.max_retries:
                    logger.warning(
                        "NVIDIA LLM tentative %s/%s echouee avec HTTP %s.",
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
                    latency_ms = (time.perf_counter() - started_perf) * 1000
                    record_model_call(
                        provider="nvidia",
                        call_type="llm",
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
                        input_summary={
                            "message_count": len(payload.get("messages", [])),
                            "max_tokens": payload.get("max_tokens"),
                            "temperature": payload.get("temperature"),
                            "seed": payload.get("seed"),
                        },
                    )
                last_error = exc
                if attempt <= self.max_retries:
                    logger.warning(
                        "NVIDIA LLM tentative %s/%s echouee: %s",
                        attempt,
                        self.max_retries + 1,
                        exc,
                    )
                    time.sleep(self.retry_delay)
                    continue
                break
        raise ExternalServiceError(f"NVIDIA LLM indisponible: {last_error}") from last_error


def get_llm_client(settings: Settings) -> NvidiaLLMClient:
    return NvidiaLLMClient(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        model=settings.llm_model,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
        retry_delay=settings.llm_retry_delay,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
        seed=settings.llm_seed,
    )


def _loads_json(text: str) -> dict[str, Any]:
    return parse_json_payload(text)


def _finish_reason(response: dict[str, Any]) -> str | None:
    try:
        return response["choices"][0].get("finish_reason")
    except (KeyError, IndexError, TypeError):
        return None
