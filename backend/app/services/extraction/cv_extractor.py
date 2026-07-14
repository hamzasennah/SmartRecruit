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


KNOWN_COMPANIES = ["Experteye", "BCP", "Renault", "Maltem Africa", "Sanlam"]


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

    def _heuristic_extract(self, document: DocumentText) -> StructuredCV:
        text = document.text
        experience_text = document.sections.get("experience") or text
        education_text = "\n".join([document.sections.get("education", ""), text])
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
    month_name = r"[^\W\d_]{3,12}"
    date_token = rf"(?:{month_name}\s+\d{{4}}|\d{{1,2}}[/.-]\d{{4}}|\d{{4}})"
    end_token = rf"(?:{date_token}|present|pr\u00e9sent|aujourd'hui|actuellement)"
    title_first_pattern = re.compile(
        rf"(?P<title>[^\n\r]{{3,120}}?)\s+"
        rf"(?P<start>{date_token})\s*(?:a|\u00e0|to|-|\u2013|\u2014)\s*"
        rf"(?P<end>{end_token})",
        re.IGNORECASE | re.UNICODE,
    )
    date_first_pattern = re.compile(
        rf"(?P<start>{date_token})\s*(?:a|\u00e0|to|-|\u2013|\u2014)\s*"
        rf"(?P<end>{end_token})\s+(?P<title>[^\n\r]{{3,160}})",
        re.IGNORECASE | re.UNICODE,
    )

    experiences: list[Experience] = []
    lines = _logical_lines(text)
    for index, line in enumerate(lines):
        match = title_first_pattern.search(line) or date_first_pattern.search(line)
        if not match:
            continue
        window = "\n".join(lines[index : index + 5])
        title = _extract_role_title(match.group("title"))
        if not _is_professional_experience_title(title):
            continue
        company = _extract_company(line, window)
        experiences.append(
            Experience(
                job_title=title,
                company=company,
                start_date=match.group("start").strip(),
                end_date=match.group("end").strip(),
                missions=_extract_mission_snippets(window),
                skills_used=_extract_known_skills(window),
                confidence=0.65 if company else 0.6,
            )
        )

    if not experiences:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:ans|annees|ann\u00e9es|years)", normalize_text(text))
        if match:
            experiences.append(Experience(declared_duration=match.group(0), confidence=0.45))
    return experiences


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


def _logical_lines(text: str) -> list[str]:
    return [line.strip() for line in re.split(r"[\n\r]+", text) if line.strip()]


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
    for raw_line in re.split(r"[\n\r\u2022]+", text):
        line = raw_line.strip(" -\u2013\u2014*")
        if 25 <= len(line) <= 220:
            snippets.append(line)
    return snippets[:6]


def _extract_education(text: str) -> list[Education]:
    education: list[Education] = []
    lines = _logical_lines(text)
    for index, line in enumerate(lines):
        context = _education_context(lines, index)
        normalized = normalize_text(context)
        if not _looks_like_education_line(normalized):
            continue
        degree = _education_degree_from_line(context)
        if not degree:
            continue
        institution = _education_institution_from_line(context)
        years = [int(year) for year in re.findall(r"(?:19|20)\d{2}", context)]
        education.append(
            Education(
                degree=degree,
                normalized_level=normalize_education_level(degree),
                institution=institution,
                start_year=years[0] if years else None,
                end_year=years[-1] if len(years) >= 2 else None,
                confidence=0.65,
            )
        )
    return _dedupe_education(education)


def _education_context(lines: list[str], index: int) -> str:
    selected = [lines[index]]
    for next_line in lines[index + 1 : index + 3]:
        if _education_degree_from_line(next_line):
            break
        selected.append(next_line)
    return "\n".join(selected)


def _looks_like_education_line(normalized: str) -> bool:
    markers = [
        "ingenieur d etat", "diplome d ingenieur", "master", "licence",
        "bachelor", "bac+5", "bac+3", "insea", "universite", "ecole",
        "faculte", "formation",
    ]
    return any(marker in normalized for marker in markers)


def _education_degree_from_line(line: str) -> str | None:
    normalized = normalize_text(line)
    degree_patterns = [
        ("ingenieur d etat", "Ingenieur d'Etat en Data et Logiciels" if "data" in normalized else "Diplome d'ingenieur"),
        ("diplome d ingenieur", "Diplome d'ingenieur"),
        ("master", "Master"),
        ("licence", "Licence"),
        ("bachelor", "Bachelor"),
        ("bac+5", "Bac+5"),
        ("bac+3", "Bac+3"),
    ]
    for marker, degree in degree_patterns:
        if marker in normalized:
            return degree
    return None


def _education_institution_from_line(line: str) -> str | None:
    known = ["INSEA", "ENSIAS", "EMSI", "UM5", "Universite", "Faculte", "Ecole"]
    normalized = normalize_text(line)
    for institution in known:
        if normalize_text(institution) in normalized:
            return institution
    return None


def _dedupe_education(values: list[Education]) -> list[Education]:
    by_degree: dict[str, Education] = {}
    result: list[Education] = []
    for item in values:
        key = normalize_text(item.degree)
        existing = by_degree.get(key)
        if not existing:
            by_degree[key] = item
            result.append(item)
            continue
        existing.institution = existing.institution or item.institution
        existing.start_year = existing.start_year or item.start_year
        existing.end_year = existing.end_year or item.end_year
    return result


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
