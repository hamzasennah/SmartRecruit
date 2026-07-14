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
    return round(sum(signals) / len(signals), 4) if signals else 0.0


def tag_relevance(experiences: list[Experience], job: StructuredJobDescription) -> list[Experience]:
    for experience in experiences:
        experience.relevance_score = calculate_experience_relevance(experience, job)
    return experiences


def _token_similarity(left: str, right: str) -> float:
    left_tokens = set(tokenize(left))
    right_tokens = set(tokenize(right))
    return len(left_tokens.intersection(right_tokens)) / len(left_tokens.union(right_tokens)) if left_tokens and right_tokens else 0.0

