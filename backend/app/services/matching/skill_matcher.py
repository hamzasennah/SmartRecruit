from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.normalization.skill_normalizer import normalize_skill_list


def match_skills(cv: StructuredCV, job: StructuredJobDescription) -> dict:
    candidate = set(normalize_skill_list(cv.skills.technical + cv.skills.tools + cv.skills.soft + [s for exp in cv.experiences for s in exp.skills_used] + [s for p in cv.projects for s in p.skills_used]))
    mandatory = normalize_skill_list(job.required_skills.mandatory)
    preferred = normalize_skill_list(job.required_skills.preferred)
    matched_mandatory = sorted(set(mandatory).intersection(candidate))
    matched_preferred = sorted(set(preferred).intersection(candidate))
    missing_mandatory = [skill for skill in mandatory if skill not in matched_mandatory]
    missing_preferred = [skill for skill in preferred if skill not in matched_preferred]
    mandatory_score = len(matched_mandatory) / len(mandatory) if mandatory else 1.0
    preferred_score = len(matched_preferred) / len(preferred) if preferred else 1.0
    return {"score": round((0.8 * mandatory_score + 0.2 * preferred_score) * 100, 2), "matched": matched_mandatory + matched_preferred, "missing": missing_mandatory + missing_preferred, "details": {"missing_mandatory_count": len(missing_mandatory)}}


def match_soft_skills(cv: StructuredCV, job: StructuredJobDescription) -> dict:
    candidate = set(normalize_skill_list(cv.skills.soft))
    required = normalize_skill_list(job.required_skills.soft)
    matched = sorted(set(required).intersection(candidate))
    missing = [skill for skill in required if skill not in matched]
    return {"score": round((len(matched) / len(required) if required else 1.0) * 100, 2), "matched": matched, "missing": missing, "details": {}}

