from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.normalization.text_normalizer import tokenize


def match_responsibilities(cv: StructuredCV, job: StructuredJobDescription, retrieved_evidence: list[dict] | None = None) -> dict:
    if not job.responsibilities:
        return {"score": 100.0, "matched": [], "missing": [], "details": {}}
    candidate_text = " ".join([m for exp in cv.experiences for m in exp.missions] + [p.description or "" for p in cv.projects])
    matched, missing = [], []
    for responsibility in job.responsibilities:
        if _similarity(responsibility, candidate_text) >= 0.12:
            matched.append(responsibility)
        else:
            missing.append(responsibility)
    score = min((len(matched) / len(job.responsibilities)) + min(len(retrieved_evidence or []) * 0.03, 0.15), 1.0)
    return {"score": round(score * 100, 2), "matched": matched, "missing": missing[:5], "details": {"retrieved_evidence_count": len(retrieved_evidence or [])}}


def _similarity(left: str, right: str) -> float:
    left_tokens, right_tokens = set(tokenize(left)), set(tokenize(right))
    return len(left_tokens.intersection(right_tokens)) / len(left_tokens) if left_tokens and right_tokens else 0.0

