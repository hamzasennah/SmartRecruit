from app.infrastructure.postgres_vector_store import _search_sort_key, _vector_literal


def test_vector_literal_uses_pgvector_format() -> None:
    assert _vector_literal([1, 0.5, -2]) == "[1,0.5,-2]"


def test_search_sort_key_is_deterministic_for_equal_scores() -> None:
    rows = [
        {"id": "b", "score": 0.9, "metadata": {"document_id": "cv2", "section": "skills", "chunk_index": 0}},
        {"id": "a", "score": 0.9, "metadata": {"document_id": "cv1", "section": "skills", "chunk_index": 0}},
        {"id": "c", "score": 0.8, "metadata": {"document_id": "cv0", "section": "skills", "chunk_index": 0}},
    ]

    ordered = sorted(rows, key=_search_sort_key)

    assert [row["id"] for row in ordered] == ["a", "b", "c"]
