from app.services.extraction.coercion import coerce_int, coerce_scalar, coerce_string_list, coerce_year


def test_shared_coercion_helpers_keep_llm_payload_tolerant() -> None:
    assert coerce_scalar({"name": "Python"}, preferred_keys=("name",)) == "Python"
    assert coerce_string_list([{"skill": "SQL"}, "Power BI"], preferred_keys=("skill",)) == ["SQL", "Power BI"]
    assert coerce_int("minimum 5 years", default=0) == 5
    assert coerce_year("2024-06") == 2024

# Role dans le projet:
# Ce fichier contient les tests unitaires pour extraction coercion. Il protege le comportement existant pendant les refactors sans appeler les services externes.
