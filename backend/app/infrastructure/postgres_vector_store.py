from __future__ import annotations

import json
from uuid import uuid4

from app.config import Settings
from app.core.exceptions import ExternalServiceError
from app.database.models import Base, VectorChunkRecord


class PostgresVectorStore:
    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ExternalServiceError("DATABASE_URL est obligatoire pour stocker les vecteurs dans PostgreSQL.")
        try:
            from sqlalchemy import create_engine, delete, select
            from sqlalchemy.exc import SQLAlchemyError
            from sqlalchemy.orm import sessionmaker
        except ImportError as exc:
            raise ExternalServiceError("SQLAlchemy est requis pour utiliser PostgreSQL.") from exc
        self._delete = delete
        self._select = select
        self._sqlalchemy_error = SQLAlchemyError
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._session_factory = sessionmaker(bind=self._engine)
        try:
            Base.metadata.create_all(self._engine)
        except SQLAlchemyError as exc:
            raise ExternalServiceError(f"PostgreSQL indisponible: {exc}") from exc

    def reset_namespace(self, namespace: str) -> None:
        try:
            with self._session_factory() as session:
                session.execute(self._delete(VectorChunkRecord).where(VectorChunkRecord.namespace == namespace))
                session.commit()
        except self._sqlalchemy_error as exc:
            raise ExternalServiceError(f"Erreur PostgreSQL pendant le nettoyage des vecteurs: {exc}") from exc

    def upsert(self, namespace: str, chunks: list[dict], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Nombre de chunks different du nombre de vecteurs.")
        try:
            with self._session_factory() as session:
                for chunk, vector in zip(chunks, vectors):
                    metadata = chunk.get("metadata", {})
                    session.add(
                        VectorChunkRecord(
                            id=str(uuid4()),
                            namespace=namespace,
                            document_id=str(metadata.get("document_id", "")),
                            section=str(metadata.get("section", "")),
                            chunk_index=int(metadata.get("chunk_index", 0)),
                            text=chunk["text"],
                            vector_json=json.dumps(vector),
                        )
                    )
                session.commit()
        except self._sqlalchemy_error as exc:
            raise ExternalServiceError(f"Erreur PostgreSQL pendant l'indexation vectorielle: {exc}") from exc

    def search(self, namespace: str, query_vector: list[float], top_k: int, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        statement = self._select(VectorChunkRecord).where(VectorChunkRecord.namespace == namespace)
        if "document_id" in filters:
            statement = statement.where(VectorChunkRecord.document_id == str(filters["document_id"]))
        if "section" in filters:
            statement = statement.where(VectorChunkRecord.section == str(filters["section"]))
        try:
            with self._session_factory() as session:
                rows = list(session.execute(statement).scalars())
        except self._sqlalchemy_error as exc:
            raise ExternalServiceError(f"Erreur PostgreSQL pendant la recherche vectorielle: {exc}") from exc
        scored = []
        for row in rows:
            vector = json.loads(row.vector_json)
            scored.append(
                {
                    "id": row.id,
                    "text": row.text,
                    "metadata": {
                        "document_id": row.document_id,
                        "section": row.section,
                        "chunk_index": row.chunk_index,
                    },
                    "score": _cosine(query_vector, vector),
                }
            )
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:top_k]


def get_vector_store(settings: Settings) -> PostgresVectorStore:
    return PostgresVectorStore(settings.database_url)


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0
