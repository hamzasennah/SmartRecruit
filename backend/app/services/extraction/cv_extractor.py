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
            cv = validate_model(
                self._llm.generate_json(CV_EXTRACTION_PROMPT.format(text=document.text[:12000])),
                StructuredCV,
            )
        else:
            cv = self._heuristic_extract(document)

        cv.skills.technical = normalize_skill_list(cv.skills.technical)
        cv.skills.tools = normalize_skill_list(cv.skills.tools)
        cv.skills.soft = normalize_skill_list(cv.skills.soft)
        for experience in cv.experiences:
            experience.skills_used = normalize_skill_list(experience.skills_used)
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

    def _heuristic_extract(self, document: DocumentText) -> StructuredCV:
        text = document.text
        experience_text = document.sections.get("experience") or text
        education_text = document.sections.get("education") or text
        project_text = document.sections.get("projects") or text
        skills = _extract_known_skills(text)
        return StructuredCV(
            candidate_name=_guess_name(document.filename, text),
            skills=SkillSet(
                technical=skills,
                tools=[skill for skill in skills if skill in {"excel", "power bi", "git", "github", "azure"}],
            ),
            experiences=_extract_experiences(experience_text),
            education=_extract_education(education_text),
            languages=_extract_languages(text),
            projects=_extract_projects(project_text),
            raw_text_preview=text[:600],
            extraction_confidence=0.45,
        )


def _guess_name(filename: str, text: str) -> str:
    first = text.splitlines()[0].strip() if text.splitlines() else ""
    if 3 <= len(first) <= 80 and not any(character.isdigit() for character in first):
        return first
    return re.sub(r"[_-]+", " ", filename.rsplit(".", 1)[0])


def _extract_known_skills(text: str) -> list[str]:
    catalog = [
        "python", "sql", "postgresql", "mysql", "power bi", "excel",
        "pandas", "numpy", "machine learning", "deep learning", "fastapi",
        "react", "typescript", "git", "github", "docker", "qdrant",
        "chromadb", "dashboard", "kpi", "snowflake", "azure", "foundry",
        "data lake", "datalake", "data visualization", "visualisation",
        "project management", "business needs", "etl", "data analysis",
        "data science",
    ]
    normalized = normalize_text(text)
    return normalize_skill_list(
        [skill for skill in catalog if normalize_text(skill) in normalized]
    )


def _extract_experiences(text: str) -> list[Experience]:
    month_name = r"[A-Za-zÀ-ÖØ-öø-ÿ]{3,12}"
    date_token = (
        rf"(?:{month_name}\s+\d{{4}}|\d{{1,2}}[/.-]\d{{4}}|\d{{4}})"
    )
    end_token = rf"(?:{date_token}|present|présent|aujourd'hui|actuellement)"
    pattern = re.compile(
        rf"(?P<title>[^\n\r]{{3,90}}?)\s+"
        rf"(?P<start>{date_token})\s*(?:a|à|to|-|–|—)\s*"
        rf"(?P<end>{end_token})",
        re.IGNORECASE | re.UNICODE,
    )

    experiences: list[Experience] = []
    for match in pattern.finditer(text):
        window = text[match.start() : min(len(text), match.end() + 700)]
        title = _clean_experience_title(match.group("title"))
        if not _is_professional_experience_title(title):
            continue
        experiences.append(
            Experience(
                job_title=title[-80:],
                start_date=match.group("start").strip(),
                end_date=match.group("end").strip(),
                missions=_extract_mission_snippets(window),
                skills_used=_extract_known_skills(window),
                confidence=0.6,
            )
        )

    if not experiences:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:ans|annees|années|years)", normalize_text(text))
        if match:
            experiences.append(Experience(declared_duration=match.group(0), confidence=0.45))
    return experiences


def _clean_experience_title(value: str) -> str:
    value = re.sub(r"^[•\-–—*\s]+", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" :;-")


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
        "analyst", "analyste", "backend", "bi", "chef de projet",
        "consultant", "data engineer", "data scientist", "developer",
        "developpeur", "devops", "engineer", "frontend", "full stack",
        "ingenieur", "intern", "lead", "manager", "project manager",
        "responsable", "software", "stage", "stagiaire", "support",
        "technicien",
    ]
    return any(marker in normalized for marker in role_markers)


def _extract_mission_snippets(text: str) -> list[str]:
    snippets: list[str] = []
    for raw_line in re.split(r"[\n\r•]+", text):
        line = raw_line.strip(" -–—*")
        if 25 <= len(line) <= 220:
            snippets.append(line)
    return snippets[:6]


def _extract_education(text: str) -> list[Education]:
    normalized = normalize_text(text)
    return [
        Education(degree=label, normalized_level=label, confidence=0.55)
        for label in ["bac+5", "master", "diplome d'ingenieur", "licence", "bachelor", "doctorat"]
        if label in normalized
    ]


def _extract_languages(text: str) -> list[Language]:
    normalized = normalize_text(text)
    return [
        Language(language=language, confidence=0.6)
        for language in ["francais", "anglais", "arabe", "espagnol"]
        if language in normalized
    ]


def _extract_projects(text: str) -> list[Project]:
    match = re.search(r"(projets?|projects?)[:\s]+(.{20,500})", text, flags=re.IGNORECASE)
    if not match:
        return []
    return [
        Project(
            description=match.group(2)[:300],
            skills_used=_extract_known_skills(match.group(2)),
        )
    ]
