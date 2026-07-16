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
FULL_RESPONSIBILITY_THRESHOLD = 70.0
PARTIAL_RESPONSIBILITY_THRESHOLD = 20.0

CONCEPT_GROUPS = {
    "dashboard_reporting": {
        "responsibility": {"dashboard", "dashbord", "tableau de bord", "kpi", "reporting"},
        "evidence": {"dashboard", "dashbord", "tableau de bord", "kpi", "reporting", "visualisation", "visualization", "tableaux de suivi"},
    },
    "data_processing": {
        "responsibility": {"data", "donnees", "snowflake", "azure", "data lake", "datalake", "disponibilite"},
        "evidence": {"data", "donnees", "sql", "azure", "traitement", "flux", "millions", "points de donnees"},
    },
    "workflow_management": {
        "responsibility": {"workstream", "project management", "piloter", "lead", "coordination"},
        "evidence": {"pilotage", "piloter", "plateforme", "coordination", "lead", "management", "projet"},
    },
    "business_needs": {
        "responsibility": {"business needs", "besoins", "metiers", "clarifier", "couverture"},
        "evidence": {"besoins", "metiers", "fonctionnel", "cahier", "specifications", "requirements", "couverture", "clarifier"},
    },
    "automation": {
        "responsibility": {"automatisation", "automatiser", "flux"},
        "evidence": {"automatisation", "automatiser", "flux"},
    },
}


def match_responsibilities(cv: StructuredCV, job: StructuredJobDescription, retrieved_evidence: list[dict] | None = None) -> dict:
    if not job.responsibilities:
        return {"applicable": False, "score": 0.0, "matched": [], "missing": [], "details": {}}
    passages = _candidate_passages(cv, retrieved_evidence)
    matched, partial, missing, matched_evidence, partial_evidence, scored = [], [], [], [], [], []
    for responsibility in job.responsibilities:
        best = _best_passage_match(responsibility, passages)
        scored.append({key: best[key] for key in ["responsibility", "score", "status", "evidence"]})
        if best["status"] == "full":
            matched.append(responsibility)
            matched_evidence.append(best["evidence"])
        elif best["status"] == "partial":
            partial.append(responsibility)
            partial_evidence.append(best["evidence"])
        else:
            missing.append(responsibility)
    score = sum(item["score"] for item in scored) / len(job.responsibilities)
    return {
        "applicable": True,
        "score": round(score, 2),
        "matched": matched,
        "missing": missing,
        "details": {
            "retrieved_evidence_count": len(retrieved_evidence or []),
            "candidate_passage_count": len(passages),
            "matched_evidence": matched_evidence[:5],
            "partial": partial,
            "partial_evidence": partial_evidence[:5],
            "responsibility_scores": scored,
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
    score = float(item.get("score", 0.0))
    return section in ALLOWED_EVIDENCE_SECTIONS and score >= MIN_RETRIEVAL_EVIDENCE_SCORE


def _best_passage_match(responsibility: str, passages: list[str]) -> dict:
    best = {"responsibility": responsibility, "status": "none", "score": 0.0, "evidence": ""}
    for passage in passages:
        score, status = _passage_match_score(responsibility, passage)
        if score > best["score"]:
            best = {
                "responsibility": responsibility,
                "status": status,
                "score": score,
                "evidence": f"{responsibility} => {passage[:220]}",
            }
    return best


def _passage_match_score(responsibility: str, passage: str) -> tuple[float, str]:
    critical_terms = _terms_in_text(responsibility)
    critical_coverage = _critical_coverage(critical_terms, passage)
    required_concepts = _required_concepts(responsibility)
    covered_concepts = _covered_concepts(required_concepts, passage)
    concept_coverage = len(covered_concepts) / len(required_concepts) if required_concepts else 0.0
    token_coverage = _token_coverage(responsibility, passage)
    score = round(max(
        (0.75 * critical_coverage + 0.25 * token_coverage) * 100,
        (0.75 * concept_coverage + 0.25 * token_coverage) * 60,
    ), 2)
    if critical_terms:
        minimum_critical = 1.0 if len(critical_terms) == 1 else 0.65
        if critical_coverage >= minimum_critical and token_coverage >= 0.18:
            return max(score, FULL_RESPONSIBILITY_THRESHOLD), "full"
        if "workflow_management" in required_concepts and "workflow_management" not in covered_concepts:
            return 0.0, "none"
        if concept_coverage > 0 and score >= PARTIAL_RESPONSIBILITY_THRESHOLD:
            return min(score, 60.0), "partial"
        return 0.0, "none"
    if score >= FULL_RESPONSIBILITY_THRESHOLD:
        return score, "full"
    if score >= PARTIAL_RESPONSIBILITY_THRESHOLD:
        return score, "partial"
    return 0.0, "none"


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


def _required_concepts(responsibility: str) -> list[str]:
    responsibility_normalized = normalize_text(responsibility)
    return [
        name
        for name, group in CONCEPT_GROUPS.items()
        if any(term in responsibility_normalized for term in group["responsibility"])
    ]


def _covered_concepts(required_concepts: list[str], passage: str) -> list[str]:
    passage_normalized = normalize_text(passage)
    covered: list[str] = []
    for name in required_concepts:
        group = CONCEPT_GROUPS[name]
        if any(term in passage_normalized for term in group["evidence"]):
            covered.append(name)
    return covered


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
