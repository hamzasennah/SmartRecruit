from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.normalization.language_normalizer import language_rank, normalize_language


def match_languages(cv: StructuredCV, job: StructuredJobDescription) -> dict:
    if not job.language_requirements:
        return {"score": 100.0, "matched": [], "missing": [], "details": {}}
    candidate = {normalize_language(l.language): language_rank(l.normalized_level or l.level) for l in cv.languages}
    matched, missing = [], []
    for req in job.language_requirements:
        lang = normalize_language(req.language)
        if candidate.get(lang, 0) >= language_rank(req.minimum_level):
            matched.append(lang)
        else:
            missing.append(lang)
    return {"score": round(len(matched) / len(job.language_requirements) * 100, 2), "matched": matched, "missing": missing, "details": {}}

