from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.normalization.language_normalizer import language_rank, normalize_language


def match_languages(cv: StructuredCV, job: StructuredJobDescription) -> dict:
    if not job.language_requirements:
        return {"applicable": False, "score": 0.0, "matched": [], "missing": [], "details": {}}
    candidate: dict[str, int] = {}
    for language in cv.languages:
        lang = normalize_language(language.language)
        if not lang:
            continue
        candidate[lang] = max(candidate.get(lang, 0), language_rank(language.normalized_level))
    matched, missing, below_required_level = [], [], []
    required_levels: dict[str, int] = {}
    for req in job.language_requirements:
        lang = normalize_language(req.language)
        if lang not in candidate:
            missing.append(lang)
            continue
        required_rank = language_rank(req.minimum_level)
        required_levels[lang] = required_rank
        matched.append(lang)
        if required_rank > 0 and 0 < candidate[lang] < required_rank:
            below_required_level.append(
                {
                    "language": lang,
                    "candidate_rank": candidate[lang],
                    "required_rank": required_rank,
                }
            )
    return {
        "applicable": True,
        "score": round(len(matched) / len(job.language_requirements) * 100, 2),
        "matched": matched,
        "missing": missing,
        "details": {
            "candidate_levels": candidate,
            "required_levels": required_levels,
            "below_required_level": below_required_level,
            "scoring_rule": "presence_based",
        },
    }
