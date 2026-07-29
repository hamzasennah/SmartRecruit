from __future__ import annotations

from app.schemas.cv import Experience
from app.schemas.job import StructuredJobDescription
from app.services.normalization.job_title_normalizer import normalize_job_title
from app.services.normalization.skill_normalizer import normalize_skill_list
from app.services.normalization.text_normalizer import tokenize


def calculate_experience_relevance(experience: Experience, job: StructuredJobDescription) -> float:
    signals: list[float] = []
    title = normalize_job_title(experience.job_title)
    preferred = [normalize_job_title(item) for item in job.experience_requirements.preferred_job_titles]
    if title and preferred:
        signals.append(1.0 if title in preferred else _token_similarity(title, " ".join(preferred)))
    required_skills = normalize_skill_list(job.required_skills.mandatory + job.required_skills.preferred)
    used_skills = normalize_skill_list(experience.skills_used)
    if required_skills:
        signals.append(len(set(required_skills).intersection(used_skills)) / len(required_skills))
    if experience.missions and job.responsibilities:
        signals.append(_token_similarity(" ".join(experience.missions), " ".join(job.responsibilities)))
    # A missing signal currently collapses to 0.0. That value is convenient for
    # arithmetic, but it does not distinguish "not relevant" from "insufficient
    # extracted data to judge".
    return round(sum(signals) / len(signals), 4) if signals else 0.0


def _token_similarity(left: str, right: str) -> float:
    left_tokens = set(tokenize(left))
    right_tokens = set(tokenize(right))
    # This is a Jaccard coefficient over normalized tokens. It is transparent,
    # but long relevant texts can be penalized because unrelated extra tokens
    # increase the union faster than the intersection.
    return len(left_tokens.intersection(right_tokens)) / len(left_tokens.union(right_tokens)) if left_tokens and right_tokens else 0.0


# Role dans le projet:
# Ce fichier estime la pertinence d'une experience pour un job. Le matcher d'experience l'utilise pour separer mois totaux et mois pertinents.
