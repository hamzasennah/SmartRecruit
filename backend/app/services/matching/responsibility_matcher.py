from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.normalization.text_normalizer import normalize_text, tokenize


STOPWORDS = {
    "a", "an", "and", "avec", "au", "aux", "by", "de", "des", "du", "en",
    "et", "for", "in", "la", "le", "les", "of", "or", "pour", "the", "to",
    "un", "une", "with",
}

CRITICAL_TERMS = [
    "power bi",
    "excel",
    "foundry",
    "snowflake",
    "azure",
    "spm",
    "itms",
    "kpi",
    "dashboard",
    "dashbord",
    "data lake",
    "datalake",
    "project management",
    "business needs",
    "supply chain",
    "packaging",
]

ALLOWED_EVIDENCE_SECTIONS = {"experience", "experiences", "projects", "responsibilities", "skills"}
MIN_RETRIEVAL_EVIDENCE_SCORE = 0.2


def match_responsibilities(cv: StructuredCV, job: StructuredJobDescription, retrieved_evidence: list[dict] | None = None) -> dict:
    if not job.responsibilities:
        return {"applicable": False, "score": 0.0, "matched": [], "missing": [], "details": {}}
    passages = _candidate_passages(cv, retrieved_evidence)
    matched, missing, matched_evidence = [], [], []
    for responsibility in job.responsibilities:
        best = _best_passage_match(responsibility, passages)
        if best["matched"]:
            matched.append(responsibility)
            matched_evidence.append(best["evidence"])
        else:
            missing.append(responsibility)
    score = len(matched) / len(job.responsibilities)
    return {
        "applicable": True,
        "score": round(score * 100, 2),
        "matched": matched,
        "missing": missing[:5],
        "details": {
            "retrieved_evidence_count": len(retrieved_evidence or []),
            "candidate_passage_count": len(passages),
            "matched_evidence": matched_evidence[:5],
        },
    }


def _candidate_passages(cv: StructuredCV, retrieved_evidence: list[dict] | None) -> list[str]:
    passages = [mission for experience in cv.experiences for mission in experience.missions]
    passages.extend(project.description or "" for project in cv.projects)
    for item in retrieved_evidence or []:
        if _is_relevant_retrieved_evidence(item):
            passages.append(str(item.get("text", "")))
    return _dedupe([passage for passage in passages if len(passage.strip()) >= 20])


def _is_relevant_retrieved_evidence(item: dict) -> bool:
    metadata = item.get("metadata", {}) or {}
    section = normalize_text(str(metadata.get("section", "")))
    score = float(item.get("rerank_score", item.get("score", 0.0)))
    return section in ALLOWED_EVIDENCE_SECTIONS and score >= MIN_RETRIEVAL_EVIDENCE_SCORE


def _best_passage_match(responsibility: str, passages: list[str]) -> dict:
    best = {"matched": False, "score": 0.0, "evidence": ""}
    for passage in passages:
        score, matched = _passage_match_score(responsibility, passage)
        if score > best["score"]:
            best = {
                "matched": matched,
                "score": score,
                "evidence": f"{responsibility} => {passage[:220]}",
            }
    return best


def _passage_match_score(responsibility: str, passage: str) -> tuple[float, bool]:
    critical_terms = _terms_in_text(responsibility)
    critical_coverage = _critical_coverage(critical_terms, passage)
    token_coverage = _token_coverage(responsibility, passage)
    score = round((0.7 * critical_coverage) + (0.3 * token_coverage), 4)
    if critical_terms:
        minimum_critical = 1.0 if len(critical_terms) == 1 else 0.65
        return score, critical_coverage >= minimum_critical and token_coverage >= 0.18
    return score, token_coverage >= 0.45


def _critical_coverage(terms: list[str], text: str) -> float:
    if not terms:
        return 0.0
    normalized = normalize_text(text)
    covered = sum(1 for term in terms if normalize_text(term) in normalized)
    return covered / len(terms)


def _token_coverage(left: str, right: str) -> float:
    left_tokens = _meaningful_tokens(left)
    right_tokens = _meaningful_tokens(right)
    return len(left_tokens.intersection(right_tokens)) / len(left_tokens) if left_tokens and right_tokens else 0.0


def _meaningful_tokens(value: str) -> set[str]:
    return {token for token in tokenize(value) if token not in STOPWORDS and len(token) > 2}


def _terms_in_text(text: str) -> list[str]:
    normalized = normalize_text(text)
    return [term for term in CRITICAL_TERMS if normalize_text(term) in normalized]


def _dedupe(values: list[str]) -> list[str]:
    seen, result = set(), []
    for value in values:
        key = normalize_text(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result
