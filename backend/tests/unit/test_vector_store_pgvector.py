from app.infrastructure.postgres_vector_store import _vector_literal


def test_vector_literal_uses_pgvector_format() -> None:
    assert _vector_literal([1, 0.5, -2]) == "[1,0.5,-2]"
