from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.normalization.language_normalizer import language_rank, normalize_language

LEVEL_LABELS_BY_RANK = {
    0: "non precise",
    1: "A1",
    2: "A2 / basique",
    3: "B1 / intermediaire",
    4: "professionnel",
    5: "courant",
    6: "bilingue",
    7: "natif",
}
UNKNOWN_LEVEL_LANGUAGE_CREDIT = 0.6


def match_languages(cv: StructuredCV, job: StructuredJobDescription) -> dict:
    if not job.language_requirements:
        # Absence of language requirements is treated as not applicable rather
        # than as a failed category.
        return {"applicable": False, "score": 0.0, "matched": [], "missing": [], "details": {}}
    candidate: dict[str, int] = {}
    candidate_level_labels: dict[str, str] = {}
    level_sources: dict[str, str] = {}
    for language in cv.languages:
        lang = normalize_language(language.language)
        if not lang:
            continue
        rank = language_rank(language.normalized_level)
        if rank >= candidate.get(lang, 0):
            candidate[lang] = rank
            candidate_level_labels[lang] = _level_label(rank)
            level_sources[lang] = _level_source(language)
    matched, missing, below_required_level = [], [], []
    below_required_level_display = []
    credits: list[float] = []
    required_levels: dict[str, int] = {}
    required_level_labels: dict[str, str] = {}
    for req in job.language_requirements:
        lang = normalize_language(req.language)
        if lang not in candidate:
            missing.append(lang)
            credits.append(0.0)
            continue
        required_rank = language_rank(req.minimum_level)
        required_levels[lang] = required_rank
        required_level_labels[lang] = _level_label(required_rank)
        matched.append(lang)
        candidate_rank = candidate[lang]
        if required_rank <= 0:
            # If the job mentions a language without a level, presence is enough
            # to earn full credit for that language.
            credits.append(1.0)
        else:
            # Rank ratios give partial credit for being below the requested
            # level, but the ordinal gaps are heuristic rather than psychometric.
            credits.append(min(candidate_rank / required_rank, 1.0) if candidate_rank > 0 else UNKNOWN_LEVEL_LANGUAGE_CREDIT)
        if required_rank > 0 and candidate_rank < required_rank:
            below_required_level.append(
                {
                    "language": lang,
                    "candidate_rank": candidate_rank,
                    "required_rank": required_rank,
                }
            )
            below_required_level_display.append(
                {
                    "language": lang,
                    "candidate_level": _level_label(candidate_rank),
                    "required_level": _level_label(required_rank),
                    "source": level_sources.get(lang, "mention du CV"),
                }
            )
    return {
        "applicable": True,
        "score": round((sum(credits) / len(job.language_requirements)) * 100, 2),
        "matched": matched,
        "missing": missing,
        "details": {
            "candidate_levels": candidate,
            "candidate_level_labels": candidate_level_labels,
            "required_levels": required_levels,
            "required_level_labels": required_level_labels,
            "level_sources": level_sources,
            "below_required_level": below_required_level,
            "below_required_level_display": below_required_level_display,
            "language_credits": credits,
            "unknown_level_credit": UNKNOWN_LEVEL_LANGUAGE_CREDIT,
            "scoring_rule": "presence_then_level_weighted",
        },
    }


def _level_label(rank: int) -> str:
    return LEVEL_LABELS_BY_RANK.get(rank, f"niveau {rank}")


def _level_source(language) -> str:
    return "infere depuis le CV" if getattr(language, "estimated", False) else "mention du CV"

# Role dans le projet:
# Ce fichier matche langues et niveaux. Il convertit les niveaux normalises en credits visibles dans les details d'audit.
