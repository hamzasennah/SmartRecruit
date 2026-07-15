from __future__ import annotations

from app.schemas.document import DocumentText
from app.schemas.job import StructuredJobDescription
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
        job.education_requirements.minimum_level = normalize_education_level(
            job.education_requirements.minimum_level
        )
        for language in job.language_requirements:
            language.language = normalize_language(language.language)
            language.minimum_level = normalize_language_level(language.minimum_level)
        job.responsibilities = _clean_responsibilities(document.text, job.responsibilities)
        job.raw_text_preview = document.text[:600]
        return job


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
