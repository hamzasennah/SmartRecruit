from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.normalization.text_normalizer import tokenize


def match_responsibilities(cv: StructuredCV, job: StructuredJobDescription, retrieved_evidence: list[dict] | None = None) -> dict:
    if not job.responsibilities:
        return {"applicable": False, "score": 0.0, "matched": [], "missing": [], "details": {}}
    evidence_texts = [
        str(item.get("text", ""))
        for item in (retrieved_evidence or [])
        if float(item.get("rerank_score", item.get("score", 0.0))) >= 0.05
    ]
    candidate_text = " ".join(
        [mission for experience in cv.experiences for mission in experience.missions]
        + [project.description or "" for project in cv.projects]
        + evidence_texts
    )
    matched, missing = [], []
    for responsibility in job.responsibilities:
        if _similarity(responsibility, candidate_text) >= 0.12:
            matched.append(responsibility)
        else:
            missing.append(responsibility)
    score = len(matched) / len(job.responsibilities)
    return {
        "applicable": True,
        "score": round(score * 100, 2),
        "matched": matched,
        "missing": missing[:5],
        "details": {"retrieved_evidence_count": len(retrieved_evidence or [])},
    }


def _similarity(left: str, right: str) -> float:
    left_tokens, right_tokens = set(tokenize(left)), set(tokenize(right))
    return len(left_tokens.intersection(right_tokens)) / len(left_tokens) if left_tokens and right_tokens else 0.0
