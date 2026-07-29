from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.core.exceptions import ExternalServiceError
from app.infrastructure.nvidia_client import NvidiaAPIClient

logger = logging.getLogger(__name__)


class NvidiaEmbeddingClient(NvidiaAPIClient):
    call_type = "embedding"
    missing_api_key_message = "NVIDIA_API_KEY est obligatoire pour appeler les embeddings NVIDIA."
    retry_log_label = "NVIDIA embeddings"
    unavailable_error_prefix = "Embeddings NVIDIA indisponibles"

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
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            logger=logger,
        )
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
            # Dimensions is optional so the service can return the model-native
            # vector size unless the deployment explicitly requests projection.
            payload["dimensions"] = self.dimensions
        response = self._post("/embeddings", payload)
        try:
            embeddings = [row["embedding"] for row in response["data"]]
        except (KeyError, TypeError) as exc:
            raise ExternalServiceError("La reponse embeddings NVIDIA n'est pas exploitable.") from exc
        if len(embeddings) != len(texts):
            # Ordering matters because callers zip embeddings back to chunks; a
            # count mismatch is safer to fail than silently misalign.
            raise ExternalServiceError("La reponse embeddings NVIDIA ne correspond pas au nombre de textes envoyes.")
        return embeddings

    def _input_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        input_values = payload.get("input", [])
        return {
            "input_type": payload.get("input_type"),
            "input_count": len(input_values) if isinstance(input_values, list) else 1,
            "dimensions": payload.get("dimensions"),
        }


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

# Role dans le projet:
# Ce fichier implemente le client d'embeddings NVIDIA. Le retrieval l'utilise pour vectoriser chunks et requetes avant stockage/recherche.
