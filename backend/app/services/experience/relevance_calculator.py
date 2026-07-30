from __future__ import annotations

import re

from app.schemas.cv import Experience
from app.schemas.job import StructuredJobDescription
from app.services.normalization.job_title_normalizer import normalize_job_title
from app.services.normalization.skill_normalizer import aliases_for_skill, normalize_skill_list
from app.services.normalization.text_normalizer import normalize_text, tokenize


def calculate_experience_relevance(experience: Experience, job: StructuredJobDescription) -> float:
    signals: list[float] = []
    non_title_signals: list[float] = []
    title = normalize_job_title(experience.job_title)
    title_score = 0.0
    target_titles = [job.job_title, *job.experience_requirements.preferred_job_titles]
    preferred = [normalize_job_title(item) for item in target_titles if normalize_job_title(item)]
    if title and preferred:
        title_score = max(_title_similarity(title, expected) for expected in preferred)
        signals.append(title_score)
    required_skills = normalize_skill_list(job.required_skills.mandatory + job.required_skills.preferred)
    used_skills = normalize_skill_list(experience.skills_used)
    if required_skills:
        mission_text = normalize_text(" ".join(experience.missions))
        skills_in_missions = [skill for skill in required_skills if _skill_is_written_in_text(skill, mission_text)]
        candidate_skills = set(used_skills).union(skills_in_missions)
        skill_signal = len(set(required_skills).intersection(candidate_skills)) / len(required_skills)
        signals.append(skill_signal)
        non_title_signals.append(skill_signal)
    if experience.missions and job.responsibilities:
        responsibility_signal = _token_similarity(" ".join(experience.missions), " ".join(job.responsibilities))
        signals.append(responsibility_signal)
        non_title_signals.append(responsibility_signal)
    # A missing signal currently collapses to 0.0. That value is convenient for
    # arithmetic, but it does not distinguish "not relevant" from "insufficient
    # extracted data to judge".
    if not signals:
        return 0.0
    score = sum(signals) / len(signals)
    if title_score >= 0.8 and any(signal > 0 for signal in non_title_signals):
        score = max(score, 0.55)
    return round(score, 4)


def _token_similarity(left: str, right: str) -> float:
    left_tokens = set(tokenize(left))
    right_tokens = set(tokenize(right))
    # This is a Jaccard coefficient over normalized tokens. It is transparent,
    # but long relevant texts can be penalized because unrelated extra tokens
    # increase the union faster than the intersection.
    return len(left_tokens.intersection(right_tokens)) / len(left_tokens.union(right_tokens)) if left_tokens and right_tokens else 0.0


def _title_similarity(title: str, expected: str) -> float:
    if not title or not expected:
        return 0.0
    if title == expected or title in expected or expected in title:
        return 1.0
    return _token_similarity(title, expected)


def _skill_is_written_in_text(skill: str, text: str) -> bool:
    for alias in aliases_for_skill(skill):
        normalized = normalize_text(alias)
        if not normalized:
            continue
        if re.search(rf"(?<!\w){re.escape(normalized)}s?(?!\w)", text):
            return True
    return False


# Role dans le projet:
# Ce fichier estime la pertinence d'une experience pour un job. Le matcher d'experience l'utilise pour separer mois totaux et mois pertinents.
