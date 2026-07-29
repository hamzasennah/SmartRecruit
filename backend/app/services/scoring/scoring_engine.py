import re

from app.schemas.matching import CandidateMatch, CategoryScore, Evidence
from app.services.matching.certification_matcher import match_certifications_and_domains
from app.services.matching.education_matcher import match_education
from app.services.matching.experience_matcher import match_experience
from app.services.matching.language_matcher import match_languages
from app.services.matching.responsibility_matcher import match_responsibilities
from app.services.matching.skill_matcher import match_skills, match_soft_skills
from app.services.normalization.text_normalizer import normalize_text
from app.services.scoring.explanation_builder import build_strengths, build_weaknesses
from app.services.scoring.weights import load_scoring_weights

DISPLAY_EVIDENCE_SECTIONS = {"experience", "experiences", "projects", "responsibilities", "skills"}
MIN_DISPLAY_EVIDENCE_SCORE = 0.2
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
URL_PATTERN = re.compile(r"\b(?:https?://|www\.)[^\s<>()]+", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<![\w%])(?:\+?\d[\d\s()./-]{7,}\d)(?![\w%])")


class ScoringEngine:
    def score_candidate(self, filename, cv, job, retrieved_evidence=None, document_sections=None) -> CandidateMatch:
        weights = load_scoring_weights()
        # Prefer parsed document sections over vector retrieval when available:
        # they are deterministic evidence, while RAG snippets depend on chunking
        # and embedding similarity.
        responsibility_evidence = _section_evidence(filename, document_sections) or retrieved_evidence
        results = {
            "technical_skills": match_skills(cv, job),
            "experience": match_experience(cv, job),
            "responsibilities": match_responsibilities(cv, job, responsibility_evidence),
            "education": match_education(cv, job),
            "languages": match_languages(cv, job),
            "certifications_domains": match_certifications_and_domains(cv, job),
            "soft_skills": match_soft_skills(cv, job),
        }
        applicable_results = {
            name: result
            for name, result in results.items()
            if result.get("applicable", True)
        }
        # Non-applicable categories return 0.0 for transport consistency, but
        # they are removed here so an unknown requirement is not treated as a
        # real penalty in the final weighted score.
        rows = [
            _category(name, result, weights, applicable_results)
            for name, result in applicable_results.items()
        ]
        evidence = _clean_retrieved_evidence(retrieved_evidence or [])
        return CandidateMatch(
            candidate_name=cv.candidate_name or filename,
            filename=filename,
            final_score=round(sum(row.weighted_score for row in rows), 2),
            category_scores=rows,
            strengths=build_strengths(rows),
            weaknesses=build_weaknesses(rows),
            evidence=evidence,
        )


def _category(name, result, weights, applicable_results) -> CategoryScore:
    # Fixed base weights are redistributed across applicable categories only.
    # This keeps totals comparable, but it also means category importance is
    # static and not yet calibrated per job family.
    active_weight_sum = sum(weights.get(category, 0.0) for category in applicable_results) or 1.0
    weight = weights.get(name, 0.0) / active_weight_sum
    score = float(result["score"])
    details = dict(result.get("details", {}))
    details["base_weight"] = round(weights.get(name, 0.0), 4)
    details["redistributed_weight"] = round(weight, 4)
    return CategoryScore(
        name=name,
        score=round(score, 2),
        weight=round(weight, 4),
        weighted_score=round(score * weight, 2),
        matched=result.get("matched", []),
        missing=result.get("missing", []),
        details=details,
    )


def _section_evidence(filename: str, document_sections: dict[str, str] | None) -> list[dict]:
    if not document_sections:
        return []
    evidence = []
    for section, text in sorted(document_sections.items()):
        normalized_section = normalize_text(section)
        if normalized_section not in DISPLAY_EVIDENCE_SECTIONS:
            continue
        stripped = str(text).strip()
        if len(stripped) < 20:
            continue
        evidence.append(
            {
                "text": stripped,
                "score": 1.0,
                "metadata": {
                    "document_id": filename,
                    "section": normalized_section,
                    "chunk_index": 0,
                    "source": "document_section",
                },
            }
        )
    return evidence


def _clean_retrieved_evidence(rows: list[dict]) -> list[Evidence]:
    evidence: list[Evidence] = []
    for item in rows:
        metadata = item.get("metadata", {}) or {}
        section = normalize_text(str(metadata.get("section", "retrieval")))
        score = float(item.get("score", 0.0))
        # Low-similarity evidence is hidden from the UI to avoid weak excerpts
        # looking authoritative; the threshold is heuristic rather than a
        # calibrated semantic confidence score.
        if section not in DISPLAY_EVIDENCE_SECTIONS or score < MIN_DISPLAY_EVIDENCE_SCORE:
            continue
        evidence.append(
            Evidence(
                source=section,
                text=redact_personal_identifiers(str(item.get("text", ""))),
                score=score,
                metadata=metadata,
            )
        )
    return evidence[:8]


def redact_personal_identifiers(text: str) -> str:
    redacted = EMAIL_PATTERN.sub("[email masque]", text)
    redacted = URL_PATTERN.sub("[url masquee]", redacted)
    return PHONE_PATTERN.sub(_redact_phone_match, redacted)


def _redact_phone_match(match: re.Match) -> str:
    value = match.group(0)
    digit_count = len(re.sub(r"\D", "", value))
    if 9 <= digit_count <= 15:
        return "[telephone masque]"
    return value

# Role dans le projet:
# Ce fichier combine tous les matchers en score final. Il applique les poids, filtre les categories non applicables et prepare les preuves.
