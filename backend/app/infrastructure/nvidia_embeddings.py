from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.config import Settings
from app.core.exceptions import ExternalServiceError
from app.core.model_audit import provider_request_id, record_model_call, utc_now_iso

logger = logging.getLogger(__name__)


class NvidiaEmbeddingClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        max_retries: int,
        retry_delay: float,
        dimensions: int | None = None,
    ) -> None:
        if not api_key:
            raise ExternalServiceError("NVIDIA_API_KEY est obligatoire pour appeler les embeddings NVIDIA.")
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.dimensions = dimensions

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, input_type="passage")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], input_type="query")[0]

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        if not texts:
            return []
        payload: dict[str, Any] = {
            "model": self.model,
            "input": texts,
            "input_type": input_type,
        }
        if self.dimensions:
            payload["dimensions"] = self.dimensions
        response = self._post("/embeddings", payload)
        try:
            embeddings = [row["embedding"] for row in response["data"]]
        except (KeyError, TypeError) as exc:
            raise ExternalServiceError("La reponse embeddings NVIDIA n'est pas exploitable.") from exc
        if len(embeddings) != len(texts):
            raise ExternalServiceError("La reponse embeddings NVIDIA ne correspond pas au nombre de textes envoyes.")
        return embeddings

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
                input_values = payload.get("input", [])
                record_model_call(
                    provider="nvidia",
                    call_type="embedding",
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
                        "input_type": payload.get("input_type"),
                        "input_count": len(input_values) if isinstance(input_values, list) else 1,
                        "dimensions": payload.get("dimensions"),
                    },
                )
                if response.status_code in {429, 500, 502, 503, 504} and attempt <= self.max_retries:
                    logger.warning(
                        "NVIDIA embeddings tentative %s/%s echouee avec HTTP %s.",
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
                    input_values = payload.get("input", [])
                    record_model_call(
                        provider="nvidia",
                        call_type="embedding",
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
                            "input_type": payload.get("input_type"),
                            "input_count": len(input_values) if isinstance(input_values, list) else 1,
                            "dimensions": payload.get("dimensions"),
                        },
                    )
                last_error = exc
                if attempt <= self.max_retries:
                    logger.warning(
                        "NVIDIA embeddings tentative %s/%s echouee: %s",
                        attempt,
                        self.max_retries + 1,
                        exc,
                    )
                    time.sleep(self.retry_delay)
                    continue
                break
        raise ExternalServiceError(f"Embeddings NVIDIA indisponibles: {last_error}") from last_error


def get_embedding_client(settings: Settings) -> NvidiaEmbeddingClient:
    return NvidiaEmbeddingClient(
        api_key=settings.nvidia_api_key,
        base_url=settings.embedding_base_url,
        model=settings.embedding_model,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
        retry_delay=settings.llm_retry_delay,
        dimensions=settings.embedding_dimensions,
    )
