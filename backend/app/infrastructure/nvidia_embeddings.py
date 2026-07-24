from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.config import Settings
from app.core.exceptions import ExternalServiceError

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
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=self.timeout)
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
