from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.normalization.education_normalizer import education_rank
from app.services.normalization.text_normalizer import normalize_text


def match_education(cv: StructuredCV, job: StructuredJobDescription) -> dict:
    required = job.education_requirements.minimum_level
    accepted_fields = [normalize_text(field) for field in job.education_requirements.accepted_fields if normalize_text(field)]
    if not required and not accepted_fields:
        # Non-applicable means the job did not state education constraints; the
        # 0.0 score is a placeholder that the scoring engine excludes.
        return {"applicable": False, "score": 0.0, "matched": [], "missing": [], "details": {}}
    # Education levels are reduced to an ordinal rank. This keeps comparisons
    # stable, but loses nuance between degrees that share the same rank.
    candidate_rank = max(
        (education_rank(education.normalized_level or education.degree) for education in cv.education),
        default=0,
    )
    required_rank = education_rank(required) if required else 0
    unknown_required_level = bool(required and required_rank == 0)
    level_ok = bool(required and required_rank > 0 and candidate_rank >= required_rank)
    field_matches = _matched_fields(cv, accepted_fields)
    field_ok = not accepted_fields or bool(field_matches)

    score_parts: list[float] = []
    if required:
        score_parts.append(100.0 if level_ok else 0.0)
    if accepted_fields:
        score_parts.append(100.0 if field_ok else 0.0)
    score = round(sum(score_parts) / len(score_parts), 2) if score_parts else 0.0
    ok = score == 100.0
    matched = []
    if level_ok and required:
        matched.append(required)
    matched.extend(field_matches)
    missing = []
    if required and not level_ok:
        missing.append(required)
    if accepted_fields and not field_ok:
        missing.extend(accepted_fields)
    return {
        "applicable": True,
        "score": score,
        "matched": matched,
        "missing": [] if ok else missing,
        "details": {
            "candidate_education_rank": candidate_rank,
            "required_education_rank": required_rank,
            "unknown_required_level": unknown_required_level,
            "accepted_fields": accepted_fields,
            "matched_fields": field_matches,
        },
    }


def _matched_fields(cv: StructuredCV, accepted_fields: list[str]) -> list[str]:
    if not accepted_fields:
        return []
    matched: list[str] = []
    for education in cv.education:
        text = normalize_text(" ".join([education.field or "", education.degree or ""]))
        for field in accepted_fields:
            # Field matching is substring-based and explainable, but it is not
            # semantic: related fields can be missed if their wording differs.
            if field and field in text and field not in matched:
                matched.append(field)
    return matched

# Role dans le projet:
# Ce fichier matche niveaux et domaines de formation. Il transforme les criteres education en score explicable.
