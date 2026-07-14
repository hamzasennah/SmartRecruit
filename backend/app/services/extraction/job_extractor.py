from __future__ import annotations

import re

from app.schemas.document import DocumentText
from app.schemas.job import EducationRequirement, ExperienceRequirement, LanguageRequirement, RequiredSkills, StructuredJobDescription
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
            job = validate_model(self._llm.generate_json(JOB_EXTRACTION_PROMPT.format(text=document.text[:12000])), StructuredJobDescription)
        else:
            job = self._heuristic_extract(document)
        job.required_skills.mandatory = normalize_skill_list(job.required_skills.mandatory)
        job.required_skills.preferred = normalize_skill_list(job.required_skills.preferred)
        job.required_skills.soft = normalize_skill_list(job.required_skills.soft)
        job.education_requirements.minimum_level = normalize_education_level(job.education_requirements.minimum_level)
        for language in job.language_requirements:
            language.language = normalize_language(language.language)
            language.minimum_level = normalize_language_level(language.minimum_level)
        job.raw_text_preview = document.text[:600]
        return job

    def _heuristic_extract(self, document: DocumentText) -> StructuredJobDescription:
        text = document.text
        skills = _extract_skills(text)
        return StructuredJobDescription(job_title=_guess_job_title(document.filename, text), required_skills=RequiredSkills(mandatory=skills[:4], preferred=skills[4:]), experience_requirements=ExperienceRequirement(minimum_months=parse_explicit_duration(text) or 0, preferred_job_titles=[_guess_job_title(document.filename, text)]), education_requirements=EducationRequirement(minimum_level=_extract_minimum_education(text)), language_requirements=_extract_languages(text), responsibilities=_extract_responsibilities(text), extraction_confidence=0.45)


def _extract_skills(text: str) -> list[str]:
    catalog = ["python","sql","postgresql","mysql","power bi","excel","pandas","numpy","machine learning","fastapi","react","typescript","git","github","docker","dashboard","etl","data analysis","data science"]
    normalized = normalize_text(text)
    return normalize_skill_list([skill for skill in catalog if normalize_text(skill) in normalized])


def _guess_job_title(filename: str, text: str) -> str:
    match = re.search(r"(data analyst|business intelligence analyst|data scientist|developpeur python|software engineer)", normalize_text(text))
    return match.group(1) if match else re.sub(r"[_-]+", " ", filename.rsplit(".", 1)[0])


def _extract_minimum_education(text: str) -> str | None:
    normalized = normalize_text(text)
    return next((label for label in ["bac+5","master","diplome d'ingenieur","bac+3","licence","doctorat"] if label in normalized), None)


def _extract_languages(text: str) -> list[LanguageRequirement]:
    normalized = normalize_text(text)
    return [LanguageRequirement(language=lang) for lang in ["francais","anglais","arabe","espagnol"] if lang in normalized]


def _extract_responsibilities(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+|[\n\r]+", text)
    signals = ["analyser","analyse","dashboard","tableau de bord","automatis","sql","reporting","donnees"]
    return [s.strip() for s in sentences if 20 <= len(s.strip()) <= 220 and any(sig in normalize_text(s) for sig in signals)][:12]

