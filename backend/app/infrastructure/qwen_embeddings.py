from __future__ import annotations

import httpx

from app.config import Settings
from app.core.exceptions import ExternalServiceError


class QwenEmbeddingClient:
    def __init__(self, base_url: str, model: str, timeout: float = 180.0) -> None:
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = httpx.post(
                f"{self.base_url}/embeddings",
                json={"model": self.model, "input": texts},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalServiceError(f"Embeddings Qwen indisponibles: {exc}") from exc
        try:
            embeddings = [row["embedding"] for row in response.json()["data"]]
        except (KeyError, TypeError) as exc:
            raise ExternalServiceError("La reponse embeddings Qwen n'est pas exploitable.") from exc
        if len(embeddings) != len(texts):
            raise ExternalServiceError("La reponse embeddings Qwen ne correspond pas au nombre de textes envoyes.")
        return embeddings


def get_embedding_client(settings: Settings) -> QwenEmbeddingClient:
    return QwenEmbeddingClient(settings.embedding_base_url, settings.embedding_model)
