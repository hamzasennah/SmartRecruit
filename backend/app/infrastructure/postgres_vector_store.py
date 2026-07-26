from __future__ import annotations

import json
from uuid import uuid4

from app.config import Settings
from app.core.exceptions import ExternalServiceError
from app.database.models import AnalysisRecord, Base, JobRecord, ResumeRecord, VectorChunkRecord


class PostgresVectorStore:
    def __init__(self, database_url: str, vector_backend: str = "pgvector") -> None:
        if not database_url:
            raise ExternalServiceError("DATABASE_URL est obligatoire pour stocker les vecteurs dans PostgreSQL.")
        try:
            from sqlalchemy import create_engine, delete, select, text
            from sqlalchemy.exc import SQLAlchemyError
            from sqlalchemy.orm import sessionmaker
        except ImportError as exc:
            raise ExternalServiceError("SQLAlchemy est requis pour utiliser PostgreSQL.") from exc
        self._delete = delete
        self._select = select
        self._text = text
        self._sqlalchemy_error = SQLAlchemyError
        self._vector_backend = vector_backend
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._session_factory = sessionmaker(bind=self._engine)
        if self._vector_backend == "json":
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
        if self._vector_backend == "pgvector":
            return self._upsert_pgvector(namespace, chunks, vectors)
        try:
            with self._session_factory() as session:
                for chunk, vector in zip(chunks, vectors, strict=True):
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

    def _upsert_pgvector(self, namespace: str, chunks: list[dict], vectors: list[list[float]]) -> None:
        statement = self._text(
            """
            INSERT INTO vector_chunks
                (id, namespace, document_id, section, chunk_index, text, vector_json, embedding)
            VALUES
                (:id, :namespace, :document_id, :section, :chunk_index, :text, :vector_json, CAST(:embedding AS vector))
            ON CONFLICT (namespace, document_id, section, chunk_index)
            DO UPDATE SET text = EXCLUDED.text, vector_json = EXCLUDED.vector_json, embedding = EXCLUDED.embedding
            """
        )
        try:
            with self._session_factory() as session:
                for chunk, vector in zip(chunks, vectors, strict=True):
                    metadata = chunk.get("metadata", {})
                    session.execute(
                        statement,
                        {
                            "id": str(uuid4()),
                            "namespace": namespace,
                            "document_id": str(metadata.get("document_id", "")),
                            "section": str(metadata.get("section", "")),
                            "chunk_index": int(metadata.get("chunk_index", 0)),
                            "text": chunk["text"],
                            "vector_json": json.dumps(vector),
                            "embedding": _vector_literal(vector),
                        },
                    )
                session.commit()
        except self._sqlalchemy_error as exc:
            raise ExternalServiceError(
                "Erreur PostgreSQL/pgvector pendant l'indexation. "
                "Verifiez que les migrations Alembic ont ete executees."
            ) from exc

    def create_resume_record(
        self,
        filename: str,
        content_hash: str,
        candidate_name: str | None = None,
        text_preview: str = "",
    ) -> str:
        record_id = str(uuid4())
        try:
            with self._session_factory() as session:
                session.add(
                    ResumeRecord(
                        id=record_id,
                        filename=filename,
                        candidate_name=candidate_name,
                        content_hash=content_hash,
                        text_preview=text_preview[:1200],
                    )
                )
                session.commit()
        except self._sqlalchemy_error as exc:
            raise ExternalServiceError(f"Erreur PostgreSQL pendant l'enregistrement du CV: {exc}") from exc
        return record_id

    def create_job_record(
        self,
        filename: str,
        content_hash: str,
        job_title: str | None = None,
        text_preview: str = "",
    ) -> str:
        record_id = str(uuid4())
        try:
            with self._session_factory() as session:
                session.add(
                    JobRecord(
                        id=record_id,
                        filename=filename,
                        job_title=job_title,
                        content_hash=content_hash,
                        text_preview=text_preview[:1200],
                    )
                )
                session.commit()
        except self._sqlalchemy_error as exc:
            raise ExternalServiceError(f"Erreur PostgreSQL pendant l'enregistrement de la fiche de poste: {exc}") from exc
        return record_id

    def create_analysis_record(
        self,
        namespace: str,
        result: dict,
        summary: str,
        total_candidates: int,
        job_id: str | None = None,
    ) -> str:
        record_id = str(uuid4())
        try:
            with self._session_factory() as session:
                session.add(
                    AnalysisRecord(
                        id=record_id,
                        namespace=namespace,
                        job_id=job_id,
                        total_candidates=total_candidates,
                        summary=summary,
                        result_json=json.dumps(result, ensure_ascii=False),
                    )
                )
                session.commit()
        except self._sqlalchemy_error as exc:
            raise ExternalServiceError(f"Erreur PostgreSQL pendant l'enregistrement de l'analyse: {exc}") from exc
        return record_id

    def search(self, namespace: str, query_vector: list[float], top_k: int, filters: dict | None = None) -> list[dict]:
        if self._vector_backend == "pgvector":
            return self._search_pgvector(namespace, query_vector, top_k, filters)
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
        return sorted(scored, key=_search_sort_key)[:top_k]

    def _search_pgvector(self, namespace: str, query_vector: list[float], top_k: int, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        where = ["namespace = :namespace"]
        params: dict[str, object] = {
            "namespace": namespace,
            "query_vector": _vector_literal(query_vector),
            "top_k": top_k,
        }
        if "document_id" in filters:
            where.append("document_id = :document_id")
            params["document_id"] = str(filters["document_id"])
        if "section" in filters:
            where.append("section = :section")
            params["section"] = str(filters["section"])
        statement = self._text(
            f"""
            SELECT id, text, document_id, section, chunk_index,
                   1 - (embedding <=> CAST(:query_vector AS vector)) AS score
            FROM vector_chunks
            WHERE {" AND ".join(where)}
            ORDER BY embedding <=> CAST(:query_vector AS vector), document_id ASC, section ASC, chunk_index ASC, id ASC
            LIMIT :top_k
            """
        )
        try:
            with self._session_factory() as session:
                rows = list(session.execute(statement, params).mappings())
        except self._sqlalchemy_error as exc:
            raise ExternalServiceError(
                "Erreur PostgreSQL/pgvector pendant la recherche vectorielle. "
                "Verifiez que les migrations Alembic ont ete executees."
            ) from exc
        return [
            {
                "id": row["id"],
                "text": row["text"],
                "metadata": {
                    "document_id": row["document_id"],
                    "section": row["section"],
                    "chunk_index": row["chunk_index"],
                },
                "score": float(row["score"] or 0.0),
            }
            for row in rows
        ]


def get_vector_store(settings: Settings) -> PostgresVectorStore:
    return PostgresVectorStore(settings.database_url, vector_backend=settings.vector_backend)


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _search_sort_key(item: dict) -> tuple[float, str, str, int, str]:
    metadata = item.get("metadata", {}) or {}
    return (
        -float(item.get("score", 0.0)),
        str(metadata.get("document_id", "")).casefold(),
        str(metadata.get("section", "")).casefold(),
        int(metadata.get("chunk_index", 0)),
        str(item.get("id", "")).casefold(),
    )


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.12g}" for value in vector) + "]"
