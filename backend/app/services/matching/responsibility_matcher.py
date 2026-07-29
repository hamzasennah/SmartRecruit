import re

from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.normalization.text_normalizer import dedupe_by_normalized_key, normalize_text, tokenize
from app.services.rules.domain_rules import get_domain_rule_section

_RESPONSIBILITY_RULES = get_domain_rule_section("responsibility")


def _rule_list(name: str) -> list[str]:
    value = _RESPONSIBILITY_RULES.get(name, [])
    return [str(item) for item in value] if isinstance(value, list) else []


def _rule_float(name: str, default: float) -> float:
    value = _RESPONSIBILITY_RULES.get(name, default)
    return float(value) if isinstance(value, int | float) else default


def _concept_groups() -> dict[str, dict[str, set[str]]]:
    value = _RESPONSIBILITY_RULES.get("concept_groups", {})
    if not isinstance(value, dict):
        return {}
    groups: dict[str, dict[str, set[str]]] = {}
    for name, raw_group in value.items():
        if not isinstance(raw_group, dict):
            continue
        group: dict[str, set[str]] = {}
        for key in ("responsibility", "evidence"):
            terms = raw_group.get(key, [])
            group[key] = {str(term) for term in terms} if isinstance(terms, list) else set()
        groups[str(name)] = group
    return groups


STOPWORDS = set(_rule_list("stopwords"))
CRITICAL_TERMS = _rule_list("critical_terms")
ALLOWED_EVIDENCE_SECTIONS = set(_rule_list("allowed_evidence_sections"))
# These thresholds and vocabularies come from domain_rules.json. They make the
# matcher configurable, but their balance across Data/BI, developer, support,
# and PM roles must be measured with representative CV fixtures.
MIN_RETRIEVAL_EVIDENCE_SCORE = _rule_float("min_retrieval_evidence_score", 0.2)
FULL_RESPONSIBILITY_THRESHOLD = _rule_float("full_responsibility_threshold", 70.0)
PARTIAL_RESPONSIBILITY_THRESHOLD = _rule_float("partial_responsibility_threshold", 20.0)
CONCEPT_GROUPS = _concept_groups()


def match_responsibilities(cv: StructuredCV, job: StructuredJobDescription, retrieved_evidence: list[dict] | None = None) -> dict:
    if not job.responsibilities:
        return {"applicable": False, "score": 0.0, "matched": [], "missing": [], "details": {}}
    passages = _candidate_passages(cv, retrieved_evidence)
    matched, partial, missing, matched_evidence, partial_evidence, scored = [], [], [], [], [], []
    optional_responsibilities = []
    for responsibility in job.responsibilities:
        best = _best_passage_match(responsibility, passages)
        if _is_non_penalizing_responsibility(responsibility):
            # Some broad responsibilities are kept for audit but excluded from
            # penalties because their evidence is often implicit or too vague
            # for keyword scoring to judge reliably.
            optional_responsibilities.append(
                {key: best[key] for key in ["responsibility", "score", "status", "evidence"]}
            )
            continue
        scored.append({key: best[key] for key in ["responsibility", "score", "status", "evidence"]})
        if best["status"] == "full":
            matched.append(responsibility)
            matched_evidence.append(best["evidence"])
        elif best["status"] == "partial":
            partial.append(responsibility)
            partial_evidence.append(best["evidence"])
        else:
            missing.append(responsibility)
    if not scored:
        return {
            "applicable": False,
            "score": 0.0,
            "matched": [],
            "missing": [],
            "details": {
                "retrieved_evidence_count": len(retrieved_evidence or []),
                "candidate_passage_count": len(passages),
                "optional_responsibilities": optional_responsibilities,
                "responsibility_scores": [],
            },
        }
    score = sum(item["score"] for item in scored) / len(scored)
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
            "optional_responsibilities": optional_responsibilities,
            "responsibility_scores": scored,
        },
    }


def _candidate_passages(cv: StructuredCV, retrieved_evidence: list[dict] | None) -> list[str]:
    passages = [mission for experience in cv.experiences for mission in experience.missions]
    passages.extend(project.description or "" for project in cv.projects)
    for item in retrieved_evidence or []:
        if _is_relevant_retrieved_evidence(item):
            passages.append(str(item.get("text", "")))
    # Short fragments are dropped to reduce noisy matches; this may lose terse
    # but valid bullet points if the extraction produced very compact missions.
    return dedupe_by_normalized_key([passage for passage in passages if len(passage.strip()) >= 20])


def _is_relevant_retrieved_evidence(item: dict) -> bool:
    metadata = item.get("metadata", {}) or {}
    section = normalize_text(str(metadata.get("section", "")))
    score = float(item.get("score", 0.0))
    return section in ALLOWED_EVIDENCE_SECTIONS and score >= MIN_RETRIEVAL_EVIDENCE_SCORE


def _best_passage_match(responsibility: str, passages: list[str]) -> dict:
    best = {"responsibility": responsibility, "status": "none", "score": 0.0, "evidence": ""}
    best_score = 0.0
    for passage in passages:
        score, status = _passage_match_score(responsibility, passage)
        if score > best_score:
            best_score = score
            best = {
                "responsibility": responsibility,
                "status": status,
                "score": score,
                "evidence": f"{responsibility} => {passage[:220]}",
            }
    return best


def _passage_match_score(responsibility: str, passage: str) -> tuple[float, str]:
    if not _passes_responsibility_context_gate(responsibility, passage):
        return 0.0, "none"
    critical_terms = _terms_in_text(responsibility)
    critical_coverage = _critical_coverage(critical_terms, passage)
    required_concepts = _required_concepts(responsibility)
    covered_concepts = _covered_concepts(required_concepts, passage)
    concept_coverage = len(covered_concepts) / len(required_concepts) if required_concepts else 0.0
    token_coverage = _token_coverage(responsibility, passage)
    # The score mixes keyword coverage and concept groups. It remains a lexical
    # heuristic, not semantic understanding, so unseen vocabulary can be missed.
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


def _passes_responsibility_context_gate(responsibility: str, passage: str) -> bool:
    responsibility_normalized = normalize_text(responsibility)
    passage_normalized = normalize_text(passage)
    if _is_data_platform_availability_responsibility(responsibility_normalized):
        # This gate prevents generic Azure or cloud mentions from proving data
        # platform responsibilities, but it also embeds a Data/BI-oriented
        # vocabulary that should be audited against other job families.
        return _has_target_data_platform(passage_normalized) and _has_data_availability_context(passage_normalized)
    if _is_workstream_responsibility(responsibility_normalized):
        return _has_workflow_signal(passage_normalized) and _has_data_or_bi_signal(passage_normalized)
    if _is_business_needs_responsibility(responsibility_normalized):
        return _has_business_needs_signal(passage_normalized)
    return True


def _is_data_platform_availability_responsibility(text: str) -> bool:
    return (
        "snowflake" in text
        or "data lake" in text
        or "datalake" in text
        or ("azure" in text and ("donnees" in text or "data" in text or "disponibilite" in text))
    )


def _is_workstream_responsibility(text: str) -> bool:
    return "workstream" in text or ("bi" in text and "data" in text and any(term in text for term in {"piloter", "lead", "project management"}))


def _is_business_needs_responsibility(text: str) -> bool:
    return any(term in text for term in {"business needs", "besoins metiers", "clarifier", "couverture"})


def _is_non_penalizing_responsibility(text: str) -> bool:
    normalized = normalize_text(text)
    return (
        _is_business_needs_responsibility(normalized)
        or _is_data_platform_availability_responsibility(normalized)
    )


def _has_target_data_platform(text: str) -> bool:
    if "snowflake" in text or "data lake" in text or "datalake" in text:
        return True
    return _has_valid_azure_data_context(text)


def _has_valid_azure_data_context(text: str) -> bool:
    if "azure" not in text:
        return False
    for match in re.finditer(r"(?<![a-z0-9+#])azure(?![a-z0-9+#])", text):
        suffix = text[match.end(): match.end() + 25].strip()
        if suffix.startswith(("ad", "devops", "dev ops", "ci", "active directory")):
            continue
        window = text[max(0, match.start() - 45): match.end() + 70]
        if _has_data_or_bi_signal(window):
            return True
    return False


def _has_data_availability_context(text: str) -> bool:
    return any(
        term in text
        for term in {
            "data",
            "donnees",
            "datalake",
            "data lake",
            "etl",
            "pipeline",
            "flux",
            "stockage",
            "warehouse",
            "datamart",
            "disponibilite",
            "available",
            "availability",
        }
    )


def _has_workflow_signal(text: str) -> bool:
    return any(term in text for term in {"pilotage", "piloter", "lead", "coordination", "management", "projet", "workstream"})


def _has_data_or_bi_signal(text: str) -> bool:
    return any(term in text for term in {"data", "donnees", "bi", "reporting", "dashboard", "dashbord", "tableau de bord", "kpi", "sql", "etl", "warehouse", "datamart"})


def _has_business_needs_signal(text: str) -> bool:
    return any(term in text for term in {"besoin", "besoins", "metier", "metiers", "requirements", "fonctionnel", "specification", "specifications", "cahier", "clarifier"})


def _critical_coverage(terms: list[str], text: str) -> float:
    if not terms:
        return 0.0
    normalized = normalize_text(text)
    covered = sum(1 for term in terms if normalize_text(term) in normalized)
    return covered / len(terms)


def _token_coverage(left: str, right: str) -> float:
    left_tokens = _meaningful_tokens(left)
    right_tokens = _meaningful_tokens(right)
    # Unlike Jaccard, this divides by the responsibility token count only. It
    # rewards coverage of the requirement, but still depends on exact tokens and
    # stopword choices from the configured rule set.
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

# Role dans le projet:
# Ce fichier matche les responsabilites du job avec missions et preuves RAG. Il contient les seuils et heuristiques les plus sensibles au vocabulaire metier.
