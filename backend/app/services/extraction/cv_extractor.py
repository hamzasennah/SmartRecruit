from __future__ import annotations

import re

from app.schemas.cv import Education, Experience, Language, Project, SkillSet, StructuredCV
from app.schemas.document import DocumentText
from app.services.experience.duration_calculator import enrich_experience_durations
from app.services.extraction.output_validator import validate_model
from app.services.extraction.prompts import CV_EXTRACTION_PROMPT
from app.services.normalization.education_normalizer import normalize_education_level
from app.services.normalization.language_normalizer import normalize_language, normalize_language_level
from app.services.normalization.skill_normalizer import normalize_skill_list
from app.services.normalization.text_normalizer import normalize_text


class CVExtractor:
    def __init__(self, llm_provider) -> None:
        self._llm = llm_provider

    def extract(self, document: DocumentText) -> StructuredCV:
        if getattr(self._llm, "enabled", False):
            cv = validate_model(self._llm.generate_json(CV_EXTRACTION_PROMPT.format(text=document.text[:12000])), StructuredCV)
        else:
            cv = self._heuristic_extract(document)
        cv.skills.technical = normalize_skill_list(cv.skills.technical)
        cv.skills.tools = normalize_skill_list(cv.skills.tools)
        cv.skills.soft = normalize_skill_list(cv.skills.soft)
        for experience in cv.experiences:
            experience.skills_used = normalize_skill_list(experience.skills_used)
        cv.experiences = enrich_experience_durations(cv.experiences)
        for education in cv.education:
            education.normalized_level = normalize_education_level(education.normalized_level or education.degree)
        for language in cv.languages:
            language.language = normalize_language(language.language)
            language.normalized_level = normalize_language_level(language.normalized_level or language.level)
        cv.raw_text_preview = document.text[:600]
        return cv

    def _heuristic_extract(self, document: DocumentText) -> StructuredCV:
        text = document.text
        skills = _extract_known_skills(text)
        return StructuredCV(candidate_name=_guess_name(document.filename, text), skills=SkillSet(technical=skills, tools=[s for s in skills if s in {"excel", "power bi", "git", "github"}]), experiences=_extract_experiences(text), education=_extract_education(text), languages=_extract_languages(text), projects=_extract_projects(text), raw_text_preview=text[:600], extraction_confidence=0.45)


def _guess_name(filename: str, text: str) -> str:
    first = text.splitlines()[0].strip() if text.splitlines() else ""
    return first if 3 <= len(first) <= 80 and not any(c.isdigit() for c in first) else re.sub(r"[_-]+", " ", filename.rsplit(".", 1)[0])


def _extract_known_skills(text: str) -> list[str]:
    catalog = ["python","sql","postgresql","mysql","power bi","excel","pandas","numpy","machine learning","deep learning","fastapi","react","typescript","git","github","docker","qdrant","chromadb","dashboard","etl","data analysis","data science"]
    normalized = normalize_text(text)
    return normalize_skill_list([skill for skill in catalog if normalize_text(skill) in normalized])


def _extract_experiences(text: str) -> list[Experience]:
    pattern = re.compile(r"(?P<title>[A-Za-zÀ-ÿ ]{3,50})\s*(?:-|—|:)\s*(?P<start>(?:[A-Za-zÀ-ÿ]+ )?\d{4}|\d{1,2}[/.-]\d{4})\s*(?:a|à|to|-|—)\s*(?P<end>(?:[A-Za-zÀ-ÿ]+ )?\d{4}|\d{1,2}[/.-]\d{4}|present|aujourd'hui|actuellement)", re.IGNORECASE)
    experiences = [Experience(job_title=m.group("title").strip(), start_date=m.group("start").strip(), end_date=m.group("end").strip(), skills_used=_extract_known_skills(m.group(0)), confidence=0.55) for m in pattern.finditer(text)]
    if not experiences:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:ans|annees|years)", normalize_text(text))
        if match:
            experiences.append(Experience(declared_duration=match.group(0), confidence=0.45))
    return experiences


def _extract_education(text: str) -> list[Education]:
    normalized = normalize_text(text)
    return [Education(degree=label, normalized_level=label, confidence=0.55) for label in ["bac+5","master","diplome d'ingenieur","licence","bachelor","doctorat"] if label in normalized]


def _extract_languages(text: str) -> list[Language]:
    normalized = normalize_text(text)
    return [Language(language=lang, confidence=0.6) for lang in ["francais","anglais","arabe","espagnol"] if lang in normalized]


def _extract_projects(text: str) -> list[Project]:
    match = re.search(r"(projets?|projects?)[:\s]+(.{20,500})", text, flags=re.IGNORECASE)
    return [Project(description=match.group(2)[:300], skills_used=_extract_known_skills(match.group(2)))] if match else []

