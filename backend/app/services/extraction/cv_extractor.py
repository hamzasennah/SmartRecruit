from __future__ import annotations

import re

from app.schemas.cv import Experience, StructuredCV
from app.schemas.document import DocumentText
from app.services.experience.duration_calculator import enrich_experience_durations
from app.services.extraction.output_validator import parse_json_payload, validate_model
from app.services.extraction.prompts import CV_EXTRACTION_PROMPT
from app.services.normalization.education_normalizer import normalize_education_level
from app.services.normalization.language_normalizer import normalize_language, normalize_language_level
from app.services.normalization.skill_normalizer import normalize_skill_list
from app.services.normalization.text_normalizer import normalize_text


KNOWN_COMPANIES = ["Experteye", "BCP", "Renault", "Maltem Africa", "Sanlam"]


class CVExtractor:
    def __init__(self, llm_client) -> None:
        self._llm = llm_client

    def extract(self, document: DocumentText) -> StructuredCV:
        raw_payload = self._llm.generate_json(CV_EXTRACTION_PROMPT.format(text=document.text[:12000]))
        cv = validate_model(_coerce_cv_payload(raw_payload), StructuredCV)

        cv.skills.technical = normalize_skill_list(cv.skills.technical)
        cv.skills.tools = normalize_skill_list(cv.skills.tools)
        cv.skills.soft = normalize_skill_list(cv.skills.soft)
        for experience in cv.experiences:
            experience.job_title = _extract_role_title(experience.job_title or "")
            experience.company = experience.company or _extract_company(
                " ".join([experience.job_title or "", " ".join(experience.missions)]),
                " ".join(experience.missions),
            )
            experience.skills_used = normalize_skill_list(experience.skills_used)
        cv.experiences = _filter_professional_experiences(cv.experiences)
        cv.experiences = enrich_experience_durations(cv.experiences)
        for education in cv.education:
            education.normalized_level = normalize_education_level(
                education.normalized_level or education.degree
            )
        for language in cv.languages:
            language.language = normalize_language(language.language)
            language.normalized_level = normalize_language_level(
                language.normalized_level or language.level
            )
        cv.raw_text_preview = document.text[:600]
        return cv


def _coerce_cv_payload(raw_payload: str | dict) -> dict:
    payload = parse_json_payload(raw_payload) if isinstance(raw_payload, str) else dict(raw_payload)
    payload["job_titles"] = _coerce_string_list(payload.get("job_titles"))
    payload["certifications"] = _coerce_string_list(payload.get("certifications"))

    skills = payload.get("skills")
    if isinstance(skills, dict):
        skills["technical"] = _coerce_string_list(skills.get("technical"))
        skills["soft"] = _coerce_string_list(skills.get("soft"))
        skills["tools"] = _coerce_string_list(skills.get("tools"))

    for experience in payload.get("experiences") or []:
        if not isinstance(experience, dict):
            continue
        experience["missions"] = _coerce_string_list(experience.get("missions"), preferred_keys=("mission", "description", "text"))
        experience["skills_used"] = _coerce_string_list(experience.get("skills_used"), preferred_keys=("skill", "name", "tool", "technology"))

    for project in payload.get("projects") or []:
        if not isinstance(project, dict):
            continue
        project["description"] = _coerce_scalar(project.get("description"), preferred_keys=("description", "mission", "text"))
        project["skills_used"] = _coerce_string_list(project.get("skills_used"), preferred_keys=("skill", "name", "tool", "technology"))

    return payload


def _coerce_string_list(value, preferred_keys: tuple[str, ...] = ("value", "name", "text")) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return [str(value)]
    result: list[str] = []
    for item in value:
        scalar = _coerce_scalar(item, preferred_keys)
        if scalar:
            result.append(scalar)
    return result


def _coerce_scalar(value, preferred_keys: tuple[str, ...] = ("value", "name", "text")) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in preferred_keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        for candidate in value.values():
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        return None
    return str(value)


def _filter_professional_experiences(experiences: list[Experience]) -> list[Experience]:
    return [
        experience
        for experience in experiences
        if _is_professional_experience_title(experience.job_title or "")
    ]


def _clean_experience_title(value: str) -> str:
    value = re.sub(r"^[\u2022\-\u2013\u2014*\s]+", "", value)
    value = re.sub(r"^[.:,;|/\\\s]+", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" :;-")


def _extract_role_title(value: str) -> str:
    cleaned = _clean_experience_title(value)
    role_pattern = re.compile(
        r"(data analyst|data scientist|data engineer|developpeur\s+[^,;|]{0,60}|"
        r"d\u00e9veloppeur\s+[^,;|]{0,60}|developer\s+[^,;|]{0,60}|"
        r"full\s*stack\s+[^,;|]{0,60}|frontend\s+[^,;|]{0,60}|backend\s+[^,;|]{0,60}|"
        r"ingenieur\s+[^,;|]{0,60}|ing\u00e9nieur\s+[^,;|]{0,60}|"
        r"consultant\s+[^,;|]{0,60}|chef de projet\s+[^,;|]{0,60}|"
        r"stagiaire\s+[^,;|]{0,60}|stage\s+[^,;|]{0,60}|support\s+[^,;|]{0,60})",
        flags=re.IGNORECASE,
    )
    matches = list(role_pattern.finditer(cleaned))
    if matches:
        cleaned = matches[-1].group(0)
    cleaned = re.split(r"\s{2,}| chez | at | - | \| ", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    return _clean_experience_title(cleaned)[:80]


def _extract_company(line: str, window: str) -> str | None:
    combined = f"{line}\n{window}"
    normalized = normalize_text(combined)
    for company in KNOWN_COMPANIES:
        if normalize_text(company) in normalized:
            return company
    match = re.search(r"(?:chez|at)\s+([A-Z][A-Za-z0-9& .'-]{2,40})", combined)
    if match:
        return match.group(1).strip(" .,-")
    return None


def _is_professional_experience_title(title: str) -> bool:
    normalized = normalize_text(title)
    if len(normalized) < 3:
        return False
    education_markers = [
        "bachelor", "baccalaureat", "cycle preparatoire", "diplome",
        "ecole", "faculte", "formation", "ingenieur d etat", "licence",
        "master", "universite",
    ]
    if any(marker in normalized for marker in education_markers):
        return False
    mission_starters = [
        "conception", "creation", "developpement", "integration", "mise en place",
        "patients", "python", "que l integration", "realisation",
    ]
    if any(normalized.startswith(marker) for marker in mission_starters):
        return False
    role_markers = [
        "analyst", "analyste", "bi", "chef de projet",
        "consultant", "data engineer", "data scientist", "developer",
        "developpeur", "devops", "engineer", "frontend", "full stack",
        "ingenieur", "intern", "lead", "manager", "project manager",
        "responsable", "software", "stage", "stagiaire", "support",
        "technicien",
    ]
    return any(marker in normalized for marker in role_markers)
