from app.services.normalization.language_normalizer import language_rank, normalize_language
from app.services.normalization.skill_normalizer import normalize_skill
from app.services.normalization.text_normalizer import dedupe_by_normalized_key, normalize_text


def test_normalize_text_removes_accents_and_noise() -> None:
    assert normalize_text("  Février_2024 / Power-BI  ") == "fevrier 2024 power bi"


def test_skill_aliases() -> None:
    assert normalize_skill("PowerBI") == "power bi"
    assert normalize_skill("Python3") == "python"


def test_language_alias_and_rank() -> None:
    assert normalize_language("English") == "anglais"
    assert language_rank("C1") > language_rank("B1")


def test_dedupe_by_normalized_key_preserves_original_value() -> None:
    assert dedupe_by_normalized_key(["Power BI", "power-bi", "SQL"]) == ["Power BI", "SQL"]


# Role dans le projet:
# Ce fichier contient les tests unitaires pour normalization. Il protege le comportement existant pendant les refactors sans appeler les services externes.
