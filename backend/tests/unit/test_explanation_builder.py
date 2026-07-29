from app.schemas.matching import CategoryScore
from app.services.scoring.explanation_builder import build_strengths, build_weaknesses


def _category(name: str, score: float, matched=None, missing=None, details=None) -> CategoryScore:
    return CategoryScore(
        name=name,
        score=score,
        weight=1.0,
        weighted_score=score,
        matched=matched or [],
        missing=missing or [],
        details=details or {},
    )


def test_explanations_use_proven_skill_details_without_inventing() -> None:
    categories = [
        _category(
            "technical_skills",
            30.0,
            details={
                "matched_mandatory": ["azure"],
                "matched_preferred": [],
                "missing_mandatory": ["power bi", "snowflake"],
                "missing_preferred": ["spm"],
            },
        ),
        _category(
            "responsibilities",
            25.0,
            missing=["Creer et ameliorer les tableaux de bord et KPI."],
            details={"partial": ["Piloter le workstream BI/Data."]},
        ),
        _category("languages", 100.0, matched=["francais", "anglais"]),
    ]

    strengths = build_strengths(categories)
    weaknesses = build_weaknesses(categories)

    assert "Competences obligatoires trouvees: azure." in strengths
    assert "Responsabilites partiellement prouvees: Piloter le workstream BI/Data." in strengths
    assert "Competences obligatoires manquantes: power bi, snowflake." in weaknesses
    assert "Competences souhaitees manquantes: spm." not in weaknesses

# Role dans le projet:
# Ce fichier contient les tests unitaires pour explanation builder. Il protege le comportement existant pendant les refactors sans appeler les services externes.
