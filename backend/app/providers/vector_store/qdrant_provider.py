from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from app.config import Settings
from app.core.exceptions import ProviderUnavailableError


@dataclass
class InMemoryVectorStore:
    rows: list[dict] = field(default_factory=list)

    def reset_namespace(self, namespace: str) -> None:
        self.rows = [row for row in self.rows if row["namespace"] != namespace]

    def upsert(self, namespace: str, chunks: list[dict], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Nombre de chunks different du nombre de vecteurs.")
        for chunk, vector in zip(chunks, vectors):
            self.rows.append({"id": str(uuid4()), "namespace": namespace, "text": chunk["text"], "metadata": chunk.get("metadata", {}), "vector": vector})

    def search(self, namespace: str, query_vector: list[float], top_k: int, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        candidates = [row for row in self.rows if row["namespace"] == namespace and all(row["metadata"].get(k) == v for k, v in filters.items())]
        scored = [{"id": row["id"], "text": row["text"], "metadata": row["metadata"], "score": _cosine(query_vector, row["vector"])} for row in candidates]
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:top_k]


def get_vector_store(settings: Settings):
    if settings.test_mode:
        return InMemoryVectorStore()
    try:
        return QdrantVectorStore(settings.qdrant_url, settings.qdrant_collection)
    except ImportError as exc:
        raise ProviderUnavailableError("qdrant-client est requis pour utiliser Qdrant.") from exc


class QdrantVectorStore:
    def __init__(self, url: str, collection: str) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models

        self._models = models
        self._client = QdrantClient(url=url)
        self._collection = collection

    def reset_namespace(self, namespace: str) -> None:
        if not self._collection_exists():
            return
        self._client.delete(
            collection_name=self._collection,
            points_selector=self._models.FilterSelector(
                filter=self._models.Filter(
                    must=[
                        self._models.FieldCondition(
                            key="namespace",
                            match=self._models.MatchValue(value=namespace),
                        )
                    ]
                )
            ),
        )

    def upsert(self, namespace: str, chunks: list[dict], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Nombre de chunks different du nombre de vecteurs.")
        if not chunks:
            return
        self._ensure_collection(len(vectors[0]))
        points = []
        for chunk, vector in zip(chunks, vectors):
            points.append(
                self._models.PointStruct(
                    id=str(uuid4()),
                    vector=vector,
                    payload={
                        "namespace": namespace,
                        "text": chunk["text"],
                        **chunk.get("metadata", {}),
                    },
                )
            )
        self._client.upsert(collection_name=self._collection, points=points)

    def search(self, namespace: str, query_vector: list[float], top_k: int, filters: dict | None = None) -> list[dict]:
        self._ensure_collection(len(query_vector))
        must = [
            self._models.FieldCondition(
                key="namespace",
                match=self._models.MatchValue(value=namespace),
            )
        ]
        for key, value in (filters or {}).items():
            must.append(
                self._models.FieldCondition(
                    key=key,
                    match=self._models.MatchValue(value=value),
                )
            )
        results = self._client.search(
            collection_name=self._collection,
            query_vector=query_vector,
            query_filter=self._models.Filter(must=must),
            limit=top_k,
        )
        return [
            {
                "id": str(item.id),
                "text": item.payload.get("text", "") if item.payload else "",
                "metadata": dict(item.payload or {}),
                "score": float(item.score),
            }
            for item in results
        ]

    def _collection_exists(self) -> bool:
        return self._client.collection_exists(collection_name=self._collection)

    def _ensure_collection(self, vector_size: int) -> None:
        if self._collection_exists():
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=self._models.VectorParams(
                size=vector_size,
                distance=self._models.Distance.COSINE,
            ),
        )


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0
