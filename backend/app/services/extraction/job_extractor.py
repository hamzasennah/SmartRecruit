from __future__ import annotations

import re

from app.schemas.document import DocumentText
from app.schemas.job import LanguageRequirement, StructuredJobDescription
from app.services.extraction.output_validator import parse_json_payload, validate_model
from app.services.extraction.prompts import JOB_EXTRACTION_PROMPT
from app.services.normalization.education_normalizer import normalize_education_level
from app.services.normalization.language_normalizer import normalize_language, normalize_language_level
from app.services.normalization.skill_normalizer import normalize_skill_list
from app.services.normalization.text_normalizer import normalize_text


class JobExtractor:
    def __init__(self, llm_client) -> None:
        self._llm = llm_client

    def extract(self, document: DocumentText) -> StructuredJobDescription:
        raw_payload = self._llm.generate_json(JOB_EXTRACTION_PROMPT.format(text=document.text[:12000]))
        job = validate_model(_coerce_job_payload(raw_payload), StructuredJobDescription)

        job.required_skills.mandatory = normalize_skill_list(job.required_skills.mandatory)
        job.required_skills.preferred = normalize_skill_list(job.required_skills.preferred)
        job.required_skills.soft = normalize_skill_list(job.required_skills.soft)
        _apply_job_text_rules(job, document.text)
        job.education_requirements.minimum_level = normalize_education_level(
            job.education_requirements.minimum_level
        )
        for language in job.language_requirements:
            language.language = normalize_language(language.language)
            language.minimum_level = normalize_language_level(language.minimum_level)
        job.responsibilities = _clean_responsibilities(document.text, job.responsibilities)
        job.raw_text_preview = document.text[:600]
        return job


def _coerce_job_payload(raw_payload: str | dict) -> dict:
    payload = parse_json_payload(raw_payload) if isinstance(raw_payload, str) else dict(raw_payload)
    payload["job_title"] = _coerce_scalar(
        payload.get("job_title"),
        preferred_keys=("job_title", "title", "name", "value", "text"),
    )

    required_skills = payload.get("required_skills")
    if isinstance(required_skills, dict):
        required_skills["mandatory"] = _coerce_string_list(
            required_skills.get("mandatory"),
            preferred_keys=("skill", "name", "tool", "technology", "value", "text"),
        )
        required_skills["preferred"] = _coerce_string_list(
            required_skills.get("preferred"),
            preferred_keys=("skill", "name", "tool", "technology", "value", "text"),
        )
        required_skills["soft"] = _coerce_string_list(
            required_skills.get("soft"),
            preferred_keys=("skill", "name", "value", "text"),
        )

    experience_requirements = payload.get("experience_requirements")
    if isinstance(experience_requirements, dict):
        experience_requirements["minimum_months"] = _coerce_int(
            experience_requirements.get("minimum_months"),
            default=0,
        )
        experience_requirements["preferred_job_titles"] = _coerce_string_list(
            experience_requirements.get("preferred_job_titles"),
            preferred_keys=("job_title", "title", "name", "value", "text"),
        )
        experience_requirements["required_domains"] = _coerce_string_list(
            experience_requirements.get("required_domains"),
            preferred_keys=("domain", "name", "value", "text"),
        )

    education_requirements = payload.get("education_requirements")
    if isinstance(education_requirements, dict):
        education_requirements["minimum_level"] = _coerce_scalar(
            education_requirements.get("minimum_level"),
            preferred_keys=("level", "degree", "name", "value", "text"),
        )
        education_requirements["accepted_fields"] = _coerce_string_list(
            education_requirements.get("accepted_fields"),
            preferred_keys=("field", "name", "value", "text"),
        )

    payload["language_requirements"] = _coerce_language_requirements(payload.get("language_requirements"))
    payload["certifications"] = _coerce_string_list(
        payload.get("certifications"),
        preferred_keys=("certification", "name", "value", "text"),
    )
    payload["responsibilities"] = _coerce_string_list(
        payload.get("responsibilities"),
        preferred_keys=("responsibility", "mission", "name", "value", "text", "description"),
    )
    return payload


def _coerce_language_requirements(value) -> list[dict]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    result: list[dict] = []
    for item in items:
        if isinstance(item, str):
            language = item.strip()
            if language:
                result.append({"language": language, "minimum_level": None})
            continue
        if not isinstance(item, dict):
            continue
        language = _coerce_scalar(
            item.get("language") or item.get("name") or item.get("lang"),
            preferred_keys=("language", "name", "value", "text"),
        )
        if language:
            result.append(
                {
                    "language": language,
                    "minimum_level": _coerce_scalar(
                        item.get("minimum_level") or item.get("level"),
                        preferred_keys=("minimum_level", "level", "name", "value", "text"),
                    ),
                }
            )
    return result


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


def _coerce_int(value, default: int = 0) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else default


LANGUAGE_SKILLS = {"french", "english", "francais", "anglais", "arabic", "arabe"}
LANGUAGE_TOKEN_MAP = {
    "french": "french",
    "francais": "francais",
    "english": "english",
    "anglais": "anglais",
    "arabic": "arabic",
    "arabe": "arabe",
}
LANGUAGE_LEVEL_TERMS = {
    "fluent",
    "courant",
    "professional",
    "professionnel",
    "native",
    "maternel",
    "bilingual",
    "bilingue",
    "advanced",
    "avance",
    "intermediate",
    "intermediaire",
}
SOFT_SKILL_TERMS = ("autonomy", "leadership", "self-driven", "self driven")
TECHNICAL_TEXT_RULES = {
    "power bi": ("mandatory", ("power bi", "powerbi")),
    "excel": ("mandatory", ("excel",)),
    "dashboard": ("mandatory", ("dashboard", "dashbord", "tableau de bord")),
    "kpi": ("mandatory", ("kpi",)),
    "snowflake": ("mandatory", ("snowflake",)),
    "azure": ("mandatory", ("azure",)),
    "foundry": ("preferred", ("foundry",)),
    "project management": ("preferred", ("project management", "gestion de projet")),
    "business needs": ("preferred", ("business needs", "besoins metiers")),
    "supply chain": ("preferred", ("supply chain",)),
    "spm": ("preferred", ("spm",)),
    "itms": ("preferred", ("itms",)),
}


def _apply_job_text_rules(job: StructuredJobDescription, text: str) -> None:
    normalized = normalize_text(text)
    if not job.job_title:
        job.job_title = _infer_job_title(text)

    mandatory, languages_from_skills, soft_from_mandatory, demoted_to_preferred = _clean_skill_bucket(
        job.required_skills.mandatory,
        demote_preferred_only=True,
        normalized_text=normalized,
    )
    preferred, more_languages, soft_from_preferred, _ = _clean_skill_bucket(
        job.required_skills.preferred,
        demote_preferred_only=False,
        normalized_text=normalized,
    )
    preferred.extend(demoted_to_preferred)
    soft, soft_languages, preferred_from_soft = _clean_soft_skill_bucket(
        job.required_skills.soft,
        normalized_text=normalized,
    )
    preferred.extend(preferred_from_soft)
    soft.extend(soft_from_mandatory + soft_from_preferred)
    languages_from_skills.extend(more_languages + soft_languages)

    for skill, (bucket, signals) in TECHNICAL_TEXT_RULES.items():
        if any(signal in normalized for signal in signals):
            if bucket == "mandatory":
                mandatory.append(skill)
            else:
                preferred.append(skill)

    for skill in SOFT_SKILL_TERMS:
        if skill in normalized:
            soft.append(skill)

    job.required_skills.mandatory = normalize_skill_list(mandatory)
    job.required_skills.preferred = normalize_skill_list(preferred)
    job.required_skills.soft = normalize_skill_list(soft)
    _add_language_requirements(job, languages_from_skills, normalized)


def _clean_skill_bucket(
    skills: list[str],
    demote_preferred_only: bool,
    normalized_text: str,
) -> tuple[list[str], list[str], list[str], list[str]]:
    kept: list[str] = []
    languages: list[str] = []
    soft: list[str] = []
    demoted_preferred: list[str] = []
    for skill in skills:
        normalized = normalize_text(skill)
        language = _language_from_skill(normalized)
        if language:
            languages.append(language)
        elif normalized in {"autonomy", "leadership", "self driven", "self-driven"}:
            soft.append(normalized)
        elif (
            demote_preferred_only
            and normalized in {"foundry", "project management"}
            and _skill_has_text_evidence(normalized, normalized_text)
        ):
            demoted_preferred.append(normalized)
        elif _skill_has_text_evidence(normalized, normalized_text):
            kept.append(skill)
    return kept, languages, soft, demoted_preferred


def _clean_soft_skill_bucket(skills: list[str], normalized_text: str) -> tuple[list[str], list[str], list[str]]:
    soft: list[str] = []
    languages: list[str] = []
    preferred: list[str] = []
    for skill in skills:
        normalized = normalize_text(skill)
        language = _language_from_skill(normalized)
        if language:
            languages.append(language)
        elif normalized == "project management":
            if _skill_has_text_evidence(normalized, normalized_text):
                preferred.append(normalized)
        elif normalized:
            soft.append(normalized)
    return soft, languages, preferred


def _language_from_skill(normalized_skill: str) -> str | None:
    if not normalized_skill:
        return None
    if normalized_skill in LANGUAGE_SKILLS:
        return normalized_skill
    for token, language in LANGUAGE_TOKEN_MAP.items():
        if not re.search(rf"\b{re.escape(token)}\b", normalized_skill):
            continue
        if len(normalized_skill.split()) <= 4 or any(term in normalized_skill for term in LANGUAGE_LEVEL_TERMS):
            return language
    return None


def _skill_has_text_evidence(skill: str, normalized_text: str) -> bool:
    if not skill:
        return False
    if skill in normalized_text:
        return True
    for canonical, (_, signals) in TECHNICAL_TEXT_RULES.items():
        if skill == canonical:
            return any(signal in normalized_text for signal in signals)
    return False


def _add_language_requirements(job: StructuredJobDescription, languages: list[str], normalized_text: str) -> None:
    if "french" in normalized_text or "francais" in normalized_text:
        languages.append("french")
    if "english" in normalized_text or "anglais" in normalized_text:
        languages.append("english")
    existing = {normalize_language(language.language) for language in job.language_requirements}
    for language in languages:
        normalized = normalize_language(language)
        if normalized and normalized not in existing:
            job.language_requirements.append(LanguageRequirement(language=normalized, minimum_level=None))
            existing.add(normalized)


def _infer_job_title(text: str) -> str | None:
    for raw_line in text.splitlines():
        line = raw_line.strip(" \t:-")
        normalized = normalize_text(line)
        if not normalized or normalized.startswith("sensitivity"):
            continue
        if normalized.startswith(("mission", "tools", "skills", "competences")):
            return None
        title_signals = ("analyst", "data analyst", "developpeur", "developer", "engineer", "ingenieur", "consultant")
        if any(signal in normalized for signal in title_signals):
            return line
    return None


def _clean_responsibilities(text: str, extracted: list[str]) -> list[str]:
    normalized = normalize_text(text)
    responsibilities: list[str] = []
    if any(signal in normalized for signal in ["dashboard", "dashbord", "tableau de bord", "kpi", "reporting"]):
        responsibilities.append("Creer et ameliorer les tableaux de bord et KPI.")
    if any(signal in normalized for signal in ["data workstream", "bi data project management", "project management", "lead data"]):
        responsibilities.append("Piloter le workstream BI/Data.")
    if any(signal in normalized for signal in ["business needs", "besoins metiers", "clarify", "covered by it solution", "couverture"]):
        responsibilities.append("Clarifier les besoins metiers et assurer leur couverture.")
    if (
        any(signal in normalized for signal in ["availability of data", "data available", "data lake", "datalake"])
        or ("snowflake" in normalized and "azure" in normalized)
    ):
        responsibilities.append("Garantir la disponibilite des donnees dans Snowflake/Azure.")
    if responsibilities:
        return _dedupe(responsibilities)
    return _dedupe([item for item in extracted if _looks_like_responsibility(item)])


def _looks_like_responsibility(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    excluded_starts = ("tools", "tool", "competences", "skills", "data analyst")
    excluded_signals = ("must", "required", "autonomy", "leadership", "excel power bi")
    if normalized.startswith(excluded_starts):
        return False
    if any(signal in normalized for signal in excluded_signals):
        return False
    action_signals = (
        "creer", "create", "enhance", "ameliorer", "piloter", "lead",
        "clarifier", "clarify", "garantir", "assurer", "availability",
        "reporting", "dashboard", "kpi", "workstream",
    )
    return any(signal in normalized for signal in action_signals)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = normalize_text(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result
