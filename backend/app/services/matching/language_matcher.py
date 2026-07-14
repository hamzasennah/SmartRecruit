from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.normalization.language_normalizer import language_rank, normalize_language


def match_languages(cv: StructuredCV, job: StructuredJobDescription) -> dict:
    if not job.language_requirements:
        return {"applicable": False, "score": 0.0, "matched": [], "missing": [], "details": {}}
    candidate = {
        normalize_language(language.language): language_rank(language.normalized_level or language.level)
        for language in cv.languages
    }
    matched, missing = [], []
    for req in job.language_requirements:
        lang = normalize_language(req.language)
        if candidate.get(lang, 0) >= language_rank(req.minimum_level):
            matched.append(lang)
        else:
            missing.append(lang)
    return {
        "applicable": True,
        "score": round(len(matched) / len(job.language_requirements) * 100, 2),
        "matched": matched,
        "missing": missing,
        "details": {},
    }
