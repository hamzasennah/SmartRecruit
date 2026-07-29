import pytest
from app.infrastructure.postgres_vector_store import PostgresVectorStore, _vector_literal


def test_vector_literal_uses_pgvector_format() -> None:
    assert _vector_literal([1, 0.5, -2]) == "[1,0.5,-2]"


def test_vector_store_rejects_unsupported_backend() -> None:
    with pytest.raises(ValueError, match="pgvector"):
        PostgresVectorStore(
            "postgresql+psycopg://smartrecruit:change_me@localhost:5432/smartrecruit",
            vector_backend="unsupported",
        )

# Role dans le projet:
# Ce fichier contient les tests unitaires pour vector store pgvector. Il protege le comportement existant pendant les refactors sans appeler les services externes.
