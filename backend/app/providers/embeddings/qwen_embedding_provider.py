from __future__ import annotations

import hashlib
import math

import httpx

from app.config import Settings
from app.core.exceptions import ProviderUnavailableError
from app.services.normalization.text_normalizer import tokenize


class QwenEmbeddingProvider:
    def __init__(self, base_url: str, model: str, timeout: float = 180.0) -> None:
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = httpx.post(f"{self.base_url}/embeddings", json={"model": self.model, "input": texts}, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Provider embeddings Qwen indisponible: {exc}") from exc
        return [row["embedding"] for row in response.json().get("data", [])]


class DeterministicEmbeddingProvider:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_hash_embedding(text) for text in texts]


def get_embedding_provider(settings: Settings):
    return DeterministicEmbeddingProvider() if settings.test_mode else QwenEmbeddingProvider(settings.embedding_base_url, settings.embedding_model)


def _hash_embedding(text: str, dimensions: int = 128) -> list[float]:
    vector = [0.0] * dimensions
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]
