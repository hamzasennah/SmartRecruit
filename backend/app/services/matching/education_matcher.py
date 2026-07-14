from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.normalization.education_normalizer import education_rank


def match_education(cv: StructuredCV, job: StructuredJobDescription) -> dict:
    required = job.education_requirements.minimum_level
    if not required:
        return {"applicable": False, "score": 0.0, "matched": [], "missing": [], "details": {}}
    candidate_rank = max(
        (education_rank(education.normalized_level or education.degree) for education in cv.education),
        default=0,
    )
    required_rank = education_rank(required)
    ok = candidate_rank >= required_rank
    return {
        "applicable": True,
        "score": 100.0 if ok else 0.0,
        "matched": [required] if ok else [],
        "missing": [] if ok else [required],
        "details": {
            "candidate_education_rank": candidate_rank,
            "required_education_rank": required_rank,
        },
    }
