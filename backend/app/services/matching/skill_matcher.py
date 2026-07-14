from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.normalization.skill_normalizer import normalize_skill_list


def match_skills(cv: StructuredCV, job: StructuredJobDescription) -> dict:
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
        return {"applicable": False, "score": 0.0, "matched": [], "missing": [], "details": {}}
    matched_mandatory = sorted(set(mandatory).intersection(candidate))
    matched_preferred = sorted(set(preferred).intersection(candidate))
    missing_mandatory = [skill for skill in mandatory if skill not in matched_mandatory]
    missing_preferred = [skill for skill in preferred if skill not in matched_preferred]
    mandatory_score = len(matched_mandatory) / len(mandatory) if mandatory else 1.0
    preferred_score = len(matched_preferred) / len(preferred) if preferred else 1.0
    return {
        "applicable": True,
        "score": round((0.8 * mandatory_score + 0.2 * preferred_score) * 100, 2),
        "matched": matched_mandatory + matched_preferred,
        "missing": missing_mandatory + missing_preferred,
        "details": {"missing_mandatory_count": len(missing_mandatory)},
    }


def match_soft_skills(cv: StructuredCV, job: StructuredJobDescription) -> dict:
    candidate = set(normalize_skill_list(cv.skills.soft))
    required = normalize_skill_list(job.required_skills.soft)
    if not required:
        return {"applicable": False, "score": 0.0, "matched": [], "missing": [], "details": {}}
    matched = sorted(set(required).intersection(candidate))
    missing = [skill for skill in required if skill not in matched]
    return {
        "applicable": True,
        "score": round((len(matched) / len(required)) * 100, 2),
        "matched": matched,
        "missing": missing,
        "details": {},
    }
