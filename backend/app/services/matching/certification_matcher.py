from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.normalization.text_normalizer import normalize_text


def match_certifications_and_domains(cv: StructuredCV, job: StructuredJobDescription) -> dict:
    required_certifications = _normalize_list(job.certifications)
    required_domains = _normalize_list(job.experience_requirements.required_domains)
    if not required_certifications and not required_domains:
        return {"applicable": False, "score": 0.0, "matched": [], "missing": [], "details": {}}

    candidate_certifications = _normalize_list(cv.certifications)
    domain_evidence = _candidate_domain_text(cv)

    matched_certifications = [
        cert for cert in required_certifications if _contains_value(candidate_certifications, cert)
    ]
    missing_certifications = [
        cert for cert in required_certifications if cert not in matched_certifications
    ]
    matched_domains = [
        domain for domain in required_domains if domain and domain in domain_evidence
    ]
    missing_domains = [
        domain for domain in required_domains if domain not in matched_domains
    ]

    score_parts: list[float] = []
    if required_certifications:
        score_parts.append(len(matched_certifications) / len(required_certifications) * 100)
    if required_domains:
        score_parts.append(len(matched_domains) / len(required_domains) * 100)
    score = round(sum(score_parts) / len(score_parts), 2) if score_parts else 0.0
    return {
        "applicable": True,
        "score": score,
        "matched": matched_certifications + matched_domains,
        "missing": missing_certifications + missing_domains,
        "details": {
            "required_certifications": required_certifications,
            "candidate_certifications": candidate_certifications,
            "matched_certifications": matched_certifications,
            "missing_certifications": missing_certifications,
            "required_domains": required_domains,
            "matched_domains": matched_domains,
            "missing_domains": missing_domains,
        },
    }


def _normalize_list(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _contains_value(values: list[str], expected: str) -> bool:
    return any(expected == value or expected in value or value in expected for value in values)


def _candidate_domain_text(cv: StructuredCV) -> str:
    parts: list[str] = []
    for experience in cv.experiences:
        parts.extend(
            [
                experience.job_title or "",
                experience.company or "",
                " ".join(experience.missions),
                " ".join(experience.skills_used),
            ]
        )
    for education in cv.education:
        parts.extend([education.field or "", education.degree or ""])
    for project in cv.projects:
        parts.extend([project.name or "", project.description or "", " ".join(project.skills_used)])
    return normalize_text(" ".join(parts))

