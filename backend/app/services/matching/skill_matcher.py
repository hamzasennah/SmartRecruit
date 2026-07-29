from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.normalization.skill_normalizer import normalize_skill_list

PARTIAL_SKILL_MATCH_WEIGHTS: dict[str, dict[str, float]] = {}
MANDATORY_SCORE_WEIGHT = 1.0
# Preferred skills are modeled as a capped bonus so they cannot compensate
# fully for missing mandatory skills. The fixed 10% bonus may still be too
# rigid for job families where optional tooling is more or less decisive.
PREFERRED_BONUS_WEIGHT = 0.10


def match_skills(cv: StructuredCV, job: StructuredJobDescription) -> dict:
    # Matching is intentionally explicit: skills are normalized and compared as
    # keywords. This is explainable, but it can miss semantically equivalent
    # wording that is absent from the alias lists.
    candidate = set(
        normalize_skill_list(
            cv.skills.technical
            + cv.skills.tools
            + cv.skills.soft
            + [skill for experience in cv.experiences for skill in experience.skills_used]
            + [skill for project in cv.projects for skill in project.skills_used]
        )
    )
    mandatory = normalize_skill_list(job.required_skills.mandatory)
    preferred = normalize_skill_list(job.required_skills.preferred)
    if not mandatory and not preferred:
        # A 0.0 score here means "not applicable", not "candidate is weak".
        # The scoring engine removes non-applicable categories before weighting.
        return {"applicable": False, "score": 0.0, "matched": [], "missing": [], "details": {}}
    matched_mandatory = sorted(set(mandatory).intersection(candidate))
    matched_preferred = sorted(set(preferred).intersection(candidate))
    partial_mandatory = _partial_skill_matches(mandatory, candidate, matched_mandatory)
    partial_preferred = _partial_skill_matches(preferred, candidate, matched_preferred)
    partial_mandatory_skills = {item["skill"] for item in partial_mandatory}
    partial_preferred_skills = {item["skill"] for item in partial_preferred}
    missing_mandatory = [
        skill for skill in mandatory
        if skill not in matched_mandatory and skill not in partial_mandatory_skills
    ]
    missing_preferred = [
        skill for skill in preferred
        if skill not in matched_preferred and skill not in partial_preferred_skills
    ]
    mandatory_credit = len(matched_mandatory) + sum(item["credit_ratio"] for item in partial_mandatory)
    preferred_credit = len(matched_preferred) + sum(item["credit_ratio"] for item in partial_preferred)
    mandatory_score = mandatory_credit / len(mandatory) if mandatory else 1.0
    preferred_score = preferred_credit / len(preferred) if preferred else 0.0
    final_score = min(100.0, mandatory_score * 100 + preferred_score * PREFERRED_BONUS_WEIGHT * 100)
    return {
        "applicable": True,
        "score": round(final_score, 2),
        "matched": matched_mandatory + matched_preferred + _partial_labels(partial_mandatory + partial_preferred),
        "missing": missing_mandatory,
        "details": {
            "matched_mandatory": matched_mandatory,
            "matched_preferred": matched_preferred,
            "partial_mandatory": partial_mandatory,
            "partial_preferred": partial_preferred,
            "missing_mandatory": missing_mandatory,
            "missing_preferred": missing_preferred,
            "mandatory_score": round(mandatory_score * 100, 2),
            "preferred_score": round(preferred_score * 100, 2),
            "mandatory_weight": MANDATORY_SCORE_WEIGHT,
            "preferred_bonus_weight": PREFERRED_BONUS_WEIGHT,
            "mandatory_count": len(mandatory),
            "preferred_count": len(preferred),
            "missing_mandatory_count": len(missing_mandatory),
            "missing_preferred_count": len(missing_preferred),
        },
    }


def _partial_skill_matches(required: list[str], candidate: set[str], exact_matches: list[str]) -> list[dict]:
    exact = set(exact_matches)
    matches: list[dict] = []
    for skill in required:
        if skill in exact:
            continue
        # Partial matches are controlled by an explicit relation table. The
        # current empty default avoids hidden assumptions, but it also means
        # near-miss skills get no credit until the table is curated.
        related = PARTIAL_SKILL_MATCH_WEIGHTS.get(skill, {})
        found = [
            (candidate_skill, credit_ratio)
            for candidate_skill, credit_ratio in related.items()
            if candidate_skill in candidate
        ]
        if not found:
            continue
        evidence, credit_ratio = max(found, key=lambda item: item[1])
        matches.append(
            {
                "skill": skill,
                "evidence": evidence,
                "credit_ratio": credit_ratio,
                "credit_percent": round(credit_ratio * 100, 2),
            }
        )
    return matches


def _partial_labels(items: list[dict]) -> list[str]:
    return [f"{item['skill']} (partiel: {item['evidence']})" for item in items]


def match_soft_skills(cv: StructuredCV, job: StructuredJobDescription) -> dict:
    candidate = set(normalize_skill_list(cv.skills.soft))
    required = normalize_skill_list(job.required_skills.soft)
    if not required:
        return {"applicable": False, "score": 0.0, "matched": [], "missing": [], "details": {}}
    matched = sorted(set(required).intersection(candidate))
    missing = [skill for skill in required if skill not in matched]
    return {
        # Soft skills are returned for audit/display but marked non-applicable
        # so subjective wording does not silently penalize the ranking.
        "applicable": False,
        "score": round((len(matched) / len(required)) * 100, 2),
        "matched": matched,
        "missing": missing,
        "details": {
            "reason": "Les soft skills sont informatifs et ne sont pas utilises comme penalite de classement.",
        },
    }

# Role dans le projet:
# Ce fichier matche competences techniques et soft skills. Il alimente la categorie la plus importante du scoring global.
