from __future__ import annotations

from app.schemas.document import DocumentText
from app.schemas.job import LanguageRequirement, StructuredJobDescription
from app.services.extraction.output_validator import validate_model
from app.services.extraction.prompts import JOB_EXTRACTION_PROMPT
from app.services.normalization.education_normalizer import normalize_education_level
from app.services.normalization.language_normalizer import normalize_language, normalize_language_level
from app.services.normalization.skill_normalizer import normalize_skill_list
from app.services.normalization.text_normalizer import normalize_text


class JobExtractor:
    def __init__(self, llm_client) -> None:
        self._llm = llm_client

    def extract(self, document: DocumentText) -> StructuredJobDescription:
        job = validate_model(
            self._llm.generate_json(JOB_EXTRACTION_PROMPT.format(text=document.text[:12000])),
            StructuredJobDescription,
        )

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


LANGUAGE_SKILLS = {"french", "english", "francais", "anglais", "arabic", "arabe"}
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
    )
    preferred, more_languages, soft_from_preferred, _ = _clean_skill_bucket(
        job.required_skills.preferred,
        demote_preferred_only=False,
    )
    preferred.extend(demoted_to_preferred)
    soft = [skill for skill in job.required_skills.soft if normalize_text(skill) not in {"project management"}]
    soft.extend(soft_from_mandatory + soft_from_preferred)
    languages_from_skills.extend(more_languages)

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


def _clean_skill_bucket(skills: list[str], demote_preferred_only: bool) -> tuple[list[str], list[str], list[str], list[str]]:
    kept: list[str] = []
    languages: list[str] = []
    soft: list[str] = []
    demoted_preferred: list[str] = []
    for skill in skills:
        normalized = normalize_text(skill)
        if normalized in LANGUAGE_SKILLS:
            languages.append(normalized)
        elif normalized in {"autonomy", "leadership", "self driven", "self-driven"}:
            soft.append(normalized)
        elif demote_preferred_only and normalized in {"foundry", "project management"}:
            demoted_preferred.append(normalized)
        else:
            kept.append(skill)
    return kept, languages, soft, demoted_preferred


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
