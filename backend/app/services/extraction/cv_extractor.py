from __future__ import annotations

from pathlib import Path
import re

from app.schemas.cv import Experience, Language, StructuredCV
from app.schemas.document import DocumentText
from app.schemas.job import StructuredJobDescription
from app.services.experience.duration_calculator import enrich_experience_durations
from app.services.extraction.output_validator import parse_json_payload, validate_model
from app.services.extraction.prompts import CV_EXTRACTION_PROMPT
from app.services.normalization.education_normalizer import normalize_education_level
from app.services.normalization.language_normalizer import normalize_language, normalize_language_level
from app.services.normalization.skill_normalizer import aliases_for_skill, normalize_skill_list
from app.services.normalization.text_normalizer import normalize_text


KNOWN_COMPANIES = ["Experteye", "BCP", "Renault", "Maltem Africa", "Sanlam"]
RAW_TEXT_SKILL_HINTS = {
    "power bi": ("power bi", "powerbi", "microsoft power bi", "ms power bi"),
    "excel": ("excel", "microsoft excel", "ms excel"),
    "snowflake": ("snowflake",),
    "azure": ("azure", "microsoft azure"),
    "azure ad": ("azure ad", "azure active directory"),
    "dashboard": ("dashboard", "dashbord", "tableau de bord", "tableaux de bord"),
    "kpi": ("kpi", "key performance indicator", "indicateur cle", "indicateurs cles"),
    "python": ("python",),
    "sql": ("sql", "structured query language"),
    "postgresql": ("postgresql", "postgres sql", "postgre sql", "postgres"),
    "mysql": ("mysql", "my sql"),
    "pandas": ("pandas",),
    "dax": ("dax",),
    "power automate": ("power automate",),
    "power apps": ("power apps", "powerapps"),
    "sharepoint": ("sharepoint", "share point"),
}
RAW_TEXT_TOOL_SKILLS = {
    "power bi",
    "excel",
    "snowflake",
    "azure",
    "azure ad",
    "dashboard",
    "dax",
    "power automate",
    "power apps",
    "sharepoint",
}
RAW_TEXT_SOFT_SKILL_HINTS = {
    "autonomy": ("autonomy", "autonomie", "autonome"),
    "leadership": ("leadership",),
    "self driven": ("self driven", "self-driven", "self starter", "selfstarter"),
}

CANDIDATE_ROLE_PATTERN = re.compile(
    r"\b(data\s+analyst|data\s+scientist|data\s+engineer|developpeur|d\u00e9veloppeur|"
    r"developer|full\s*stack|frontend|backend|ingenieur|ing\u00e9nieur|software|support|"
    r"consultant|chef\s+de\s+projet|project\s+manager)\b",
    flags=re.IGNORECASE,
)
CANDIDATE_NAME_REJECT_TERMS = {
    "adresse",
    "analyst",
    "analyste",
    "backend",
    "casablanca",
    "certification",
    "competence",
    "contact",
    "cv",
    "data",
    "developpeur",
    "developer",
    "diplome",
    "education",
    "experience",
    "frontend",
    "fullstack",
    "ingenieur",
    "kenitra",
    "langue",
    "linkedin",
    "logiciel",
    "maroc",
    "profil",
    "projet",
    "rabat",
    "resume",
    "settat",
    "software",
    "support",
    "telephone",
}
AZURE_NON_DATA_CONTEXTS = {
    "ad",
    "devops",
    "dev ops",
    "ci",
    "active directory",
}


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
            language.normalized_level = normalize_language_level(language.normalized_level)
        enrich_languages_from_raw_text(cv, document.text)
        _enrich_explicit_skills_from_raw_text(cv, document.text)
        if _candidate_name_needs_recovery(cv.candidate_name, document.filename):
            cv.candidate_name = _extract_candidate_name_from_raw_text(document.text) or cv.candidate_name
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

    payload["languages"] = _coerce_cv_languages(payload.get("languages"))

    for education in payload.get("education") or []:
        if not isinstance(education, dict):
            continue
        education["start_year"] = _coerce_year(education.get("start_year"))
        education["end_year"] = _coerce_year(education.get("end_year"))

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


def _coerce_cv_languages(value) -> list[dict]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    result: list[dict] = []
    for item in items:
        if isinstance(item, str):
            language = item.strip()
            if language:
                result.append({"language": language, "normalized_level": None})
            continue
        if not isinstance(item, dict):
            continue
        language = _coerce_scalar(
            item.get("language") or item.get("name") or item.get("lang"),
            preferred_keys=("language", "name", "value", "text"),
        )
        if not language:
            continue
        result.append(
            {
                "language": language,
                "normalized_level": _coerce_scalar(
                    item.get("normalized_level") or item.get("level"),
                    preferred_keys=("normalized_level", "level", "name", "value", "text"),
                ),
            }
        )
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


def _coerce_year(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    match = re.search(r"(19|20)\d{2}", str(value))
    return int(match.group(0)) if match else None


def _candidate_name_needs_recovery(value: str | None, filename: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    filename_stem = normalize_text(Path(filename).stem)
    return (
        ".pdf" in normalized
        or normalized == filename_stem
        or normalized == f"cv {filename_stem}"
        or normalized.startswith("cv ")
    )


def _extract_candidate_name_from_raw_text(raw_text: str) -> str | None:
    lines = [_clean_candidate_name_line(line) for line in re.split(r"[\n\r]+", raw_text)]
    for line in [line for line in lines if line][:25]:
        candidate = _candidate_name_from_line(line)
        if candidate:
            return candidate
    return None


def _clean_candidate_name_line(line: str) -> str:
    line = re.sub(r"[^\w\u00c0-\u017f' .-]+", " ", line)
    line = re.sub(r"\s+", " ", line).strip(" .-|")
    return line


def _candidate_name_from_line(line: str) -> str | None:
    if _looks_like_spaced_heading(line):
        return None
    role_match = CANDIDATE_ROLE_PATTERN.search(line)
    if role_match and role_match.start() > 4:
        line = line[: role_match.start()].strip(" .-|")
    elif role_match:
        return None
    normalized = normalize_text(line)
    if not normalized or any(term in normalized for term in CANDIDATE_NAME_REJECT_TERMS):
        return None
    if re.search(r"[@:/\\]|\d", line):
        return None
    words = [word.strip(" .,'-") for word in line.split() if word.strip(" .,'-")]
    if not 2 <= len(words) <= 5:
        return None
    if sum(1 for word in words if len(word) > 1 and word[0].isupper()) < 1:
        return None
    return " ".join(words)


def _looks_like_spaced_heading(line: str) -> bool:
    words = line.split()
    if len(words) < 5:
        return False
    return sum(1 for word in words if len(word) == 1) >= len(words) - 1


def _enrich_explicit_skills_from_raw_text(cv: StructuredCV, raw_text: str) -> None:
    normalized_text = normalize_text(raw_text)
    technical = list(cv.skills.technical)
    tools = list(cv.skills.tools)
    soft = list(cv.skills.soft)
    for canonical, aliases in RAW_TEXT_SKILL_HINTS.items():
        if not any(_contains_contextual_skill_alias(canonical, normalized_text, alias) for alias in aliases):
            continue
        if canonical in RAW_TEXT_TOOL_SKILLS:
            tools.append(canonical)
        else:
            technical.append(canonical)
    for canonical, aliases in RAW_TEXT_SOFT_SKILL_HINTS.items():
        if any(_contains_explicit_alias(normalized_text, alias) for alias in aliases):
            soft.append(canonical)
    cv.skills.technical = normalize_skill_list(technical)
    cv.skills.tools = normalize_skill_list(tools)
    cv.skills.soft = normalize_skill_list(soft)


LANGUAGE_RAW_ALIASES = {
    "francais": ("francais", "francais", "french"),
    "anglais": ("anglais", "english"),
    "arabe": ("arabe", "arabic"),
}
LANGUAGE_LEVEL_HINTS = (
    ("native", ("maternelle", "maternel", "native", "natif")),
    ("fluent", ("fluent", "courant", "courante")),
    ("professional", ("professionnel", "professionnelle", "professional", "capacite professionnelle complete")),
    ("advanced", ("avance", "advanced")),
    ("intermediate", ("intermediaire", "intermediate")),
)


def enrich_languages_from_raw_text(cv: StructuredCV, raw_text: str) -> StructuredCV:
    normalized_text = normalize_text(raw_text)
    by_language = {normalize_language(language.language): language for language in cv.languages}
    for canonical, aliases in LANGUAGE_RAW_ALIASES.items():
        match = _first_language_alias_match(normalized_text, aliases)
        if not match:
            continue
        language = by_language.get(canonical)
        if language is None:
            language = Language(language=canonical)
            cv.languages.append(language)
            by_language[canonical] = language
        if not language.normalized_level:
            language.normalized_level = _infer_language_level_from_window(normalized_text, match)
    return cv


def _first_language_alias_match(normalized_text: str, aliases: tuple[str, ...]) -> re.Match | None:
    for alias in aliases:
        normalized_alias = normalize_text(alias)
        match = re.search(
            rf"(?<![a-z0-9+#]){re.escape(normalized_alias)}(?![a-z0-9+#])",
            normalized_text,
        )
        if match:
            return match
    return None


def _infer_language_level_from_window(normalized_text: str, match: re.Match) -> str | None:
    window_start = max(0, match.start() - 45)
    window = normalized_text[window_start: match.end() + 55]
    candidates: list[tuple[int, str]] = []
    for canonical, aliases in LANGUAGE_LEVEL_HINTS:
        for alias in aliases:
            alias_index = window.find(alias)
            if alias_index >= 0:
                absolute_index = window_start + alias_index
                distance = min(abs(absolute_index - match.start()), abs(absolute_index - match.end()))
                candidates.append((distance, canonical))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def enrich_cv_with_job_skill_evidence(
    cv: StructuredCV,
    raw_text: str,
    job: StructuredJobDescription,
) -> StructuredCV:
    normalized_text = normalize_text(raw_text)
    technical = list(cv.skills.technical)
    tools = list(cv.skills.tools)
    existing = set(normalize_skill_list(technical + tools))
    requested_skills = normalize_skill_list(
        job.required_skills.mandatory + job.required_skills.preferred
    )
    for skill in requested_skills:
        if skill in existing:
            continue
        if not _skill_is_explicitly_written(skill, normalized_text):
            continue
        if skill in RAW_TEXT_TOOL_SKILLS:
            tools.append(skill)
        else:
            technical.append(skill)
        existing.add(skill)
    cv.skills.technical = normalize_skill_list(technical)
    cv.skills.tools = normalize_skill_list(tools)
    return cv


def _skill_is_explicitly_written(skill: str, normalized_text: str) -> bool:
    aliases = set(aliases_for_skill(skill))
    aliases.update(RAW_TEXT_SKILL_HINTS.get(skill, ()))
    aliases.add(skill)
    return any(
        _contains_contextual_skill_alias(skill, normalized_text, alias)
        for alias in sorted(aliases, key=len, reverse=True)
    )


def _contains_contextual_skill_alias(canonical: str, normalized_text: str, alias: str) -> bool:
    if canonical != "azure":
        return _contains_explicit_alias(normalized_text, alias)
    return _contains_azure_skill_context(normalized_text, alias)


def _contains_explicit_alias(normalized_text: str, alias: str) -> bool:
    normalized_alias = normalize_text(alias)
    if not normalized_alias:
        return False
    return re.search(
        rf"(?<![a-z0-9+#]){re.escape(normalized_alias)}(?![a-z0-9+#])",
        normalized_text,
    ) is not None


def _contains_azure_skill_context(normalized_text: str, alias: str) -> bool:
    normalized_alias = normalize_text(alias)
    if not normalized_alias:
        return False
    pattern = re.compile(rf"(?<![a-z0-9+#]){re.escape(normalized_alias)}(?![a-z0-9+#])")
    for match in pattern.finditer(normalized_text):
        window = normalized_text[match.start(): match.end() + 35]
        if any(context in window for context in AZURE_NON_DATA_CONTEXTS):
            continue
        return True
    return False


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
    if re.search(r"\b(stage|stagiaire|internship|intern|pfe)\b", normalized):
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
        "ingenieur", "lead", "manager", "project manager",
        "responsable", "software", "support",
        "technicien",
    ]
    return any(marker in normalized for marker in role_markers)
