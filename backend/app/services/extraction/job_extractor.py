from __future__ import annotations

import re

from app.schemas.document import DocumentText
from app.schemas.job import (
    EducationRequirement,
    ExperienceRequirement,
    LanguageRequirement,
    RequiredSkills,
    StructuredJobDescription,
)
from app.services.experience.duration_calculator import parse_explicit_duration
from app.services.extraction.output_validator import validate_model
from app.services.extraction.prompts import JOB_EXTRACTION_PROMPT
from app.services.normalization.education_normalizer import normalize_education_level
from app.services.normalization.language_normalizer import normalize_language, normalize_language_level
from app.services.normalization.skill_normalizer import normalize_skill_list
from app.services.normalization.text_normalizer import normalize_text


class JobExtractor:
    def __init__(self, llm_provider) -> None:
        self._llm = llm_provider

    def extract(self, document: DocumentText) -> StructuredJobDescription:
        if getattr(self._llm, "enabled", False):
            job = validate_model(
                self._llm.generate_json(JOB_EXTRACTION_PROMPT.format(text=document.text[:12000])),
                StructuredJobDescription,
            )
        else:
            job = self._heuristic_extract(document)

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

    def _heuristic_extract(self, document: DocumentText) -> StructuredJobDescription:
        text = document.text
        skills = _extract_skills(text)
        return StructuredJobDescription(
            job_title=_guess_job_title(document.filename, text),
            required_skills=RequiredSkills(mandatory=skills[:6], preferred=skills[6:]),
            experience_requirements=ExperienceRequirement(
                minimum_months=_extract_required_months(text),
                preferred_job_titles=[_guess_job_title(document.filename, text)],
            ),
            education_requirements=EducationRequirement(minimum_level=_extract_minimum_education(text)),
            language_requirements=_extract_languages(text),
            responsibilities=_extract_responsibilities(text),
            extraction_confidence=0.55,
        )


def _extract_skills(text: str) -> list[str]:
    catalog = [
        "power bi", "excel", "dashboard", "kpi", "snowflake", "azure",
        "foundry", "data lake", "datalake", "spm", "itms",
        "bi/data project management", "project management", "business needs",
        "data workstream", "packaging", "supply chain", "data analysis",
        "data science", "python", "sql", "postgresql", "mysql", "pandas",
        "numpy", "machine learning", "fastapi", "react", "typescript",
        "git", "github", "docker", "etl",
    ]
    normalized = normalize_text(text)
    return normalize_skill_list(
        [skill for skill in catalog if normalize_text(skill) in normalized]
    )


def _extract_required_months(text: str) -> int:
    explicit = parse_explicit_duration(text)
    if explicit is not None:
        return explicit
    normalized = normalize_text(text)
    if any(signal in normalized for signal in ["first experience", "premiere experience"]):
        return 12
    if "junior" in normalized:
        return 6
    return 0


def _guess_job_title(filename: str, text: str) -> str:
    match = re.search(
        r"(data analyst|business intelligence analyst|data scientist|developpeur python|software engineer)",
        normalize_text(text),
    )
    if match:
        return match.group(1)
    return re.sub(r"[_-]+", " ", filename.rsplit(".", 1)[0])


def _extract_minimum_education(text: str) -> str | None:
    normalized = normalize_text(text)
    return next(
        (
            label
            for label in ["bac+5", "master", "diplome d'ingenieur", "bac+3", "licence", "doctorat"]
            if label in normalized
        ),
        None,
    )


def _extract_languages(text: str) -> list[LanguageRequirement]:
    normalized = normalize_text(text)
    return [
        LanguageRequirement(language=language)
        for language in ["francais", "anglais", "arabe", "espagnol"]
        if language in normalized
    ]


def _extract_responsibilities(text: str) -> list[str]:
    signals = [
        "create", "enhance", "dashboard", "dashbord", "kpi", "lead",
        "data workstream", "clarify", "business needs", "covered",
        "it solution", "availability", "snowflake", "foundry", "power bi",
        "project management", "reporting", "donnees", "analyser",
        "automatis", "data",
    ]
    responsibilities: list[str] = []
    for line in _logical_lines(text):
        normalized = normalize_text(line)
        if not (18 <= len(line) <= 260):
            continue
        if normalized.startswith(("by ", "or ", "and ", "et ")):
            continue
        if any(signal in normalized for signal in signals):
            responsibilities.append(line.strip(" :;-"))
    return _dedupe(responsibilities)[:12]


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


def _logical_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in re.split(r"[\n\r]+", text):
        line = raw_line.strip()
        if not line or line in {"•", "o", "-", "–"}:
            continue
        line = re.sub(r"^[•\-–*]\s*", "", line)
        line = re.sub(r"^o\s+", "", line, flags=re.IGNORECASE)
        normalized = normalize_text(line)
        if lines and normalized.startswith(("by ", "or ", "and ", "et ", "de ", "des ")):
            lines[-1] = f"{lines[-1]} {line}"
        else:
            lines.append(line)
    return lines


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = normalize_text(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result
