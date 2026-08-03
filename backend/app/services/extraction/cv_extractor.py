from __future__ import annotations

import logging
import re
from pathlib import Path

from app.config import settings
from app.core.model_audit import model_call_context
from app.schemas.cv import Education, Experience, Language, StructuredCV
from app.schemas.document import DocumentText
from app.schemas.job import StructuredJobDescription
from app.services.experience.duration_calculator import (
    calculate_cumulative_experience,
    enrich_experience_durations,
    parse_explicit_duration,
)
from app.services.extraction.coercion import (
    coerce_scalar as _coerce_scalar,
)
from app.services.extraction.coercion import (
    coerce_string_list as _coerce_string_list,
)
from app.services.extraction.coercion import (
    coerce_year as _coerce_year,
)
from app.services.extraction.output_validator import parse_json_payload, validate_model
from app.services.extraction.prompts import CV_EXTRACTION_PROMPT
from app.services.normalization.date_normalizer import MONTH_NAME_PATTERN, has_current_start_marker, normalize_date_text
from app.services.normalization.education_normalizer import normalize_education_level
from app.services.normalization.language_normalizer import language_rank, normalize_language, normalize_language_level
from app.services.normalization.skill_normalizer import aliases_for_skill, normalize_skill_list
from app.services.normalization.text_normalizer import normalize_text
from app.services.rules.domain_rules import get_domain_rule_section

logger = logging.getLogger(__name__)


_CV_RULES = get_domain_rule_section("cv")


def _rule_list(name: str) -> list[str]:
    value = _CV_RULES.get(name, [])
    return [str(item) for item in value] if isinstance(value, list) else []


def _rule_tuple_map(name: str) -> dict[str, tuple[str, ...]]:
    value = _CV_RULES.get(name, {})
    if not isinstance(value, dict):
        return {}
    return {
        str(key): tuple(str(item) for item in values)
        for key, values in value.items()
        if isinstance(values, list)
    }


def _role_pattern(roles: list[str]) -> re.Pattern[str]:
    escaped = [re.escape(role).replace(r"\ ", r"\s+") for role in roles]
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", flags=re.IGNORECASE)


KNOWN_COMPANIES = _rule_list("known_companies")
# These raw-text hints compensate for LLM omissions by checking explicit text.
# They improve recall, but the curated vocabulary can bias detection toward
# skills and domains that already appear in domain_rules.json.
RAW_TEXT_SKILL_HINTS = _rule_tuple_map("raw_text_skill_hints")
RAW_TEXT_TOOL_SKILLS = set(_rule_list("raw_text_tool_skills"))
RAW_TEXT_SOFT_SKILL_HINTS = _rule_tuple_map("raw_text_soft_skill_hints")
CANDIDATE_ROLE_PATTERN = _role_pattern(_rule_list("candidate_roles"))
CANDIDATE_NAME_REJECT_TERMS = set(_rule_list("candidate_name_reject_terms"))
AZURE_NON_DATA_CONTEXTS = set(_rule_list("azure_non_data_contexts"))
INTERNSHIP_MARKER_RE = re.compile(r"\b(stage|stagiaire|internship|intern|pfe|alternance)\b", flags=re.IGNORECASE)
_NUMERIC_DAY_MONTH_YEAR = r"(?:\d{1,2}[/.-]\d{1,2}[/.-](?:19\d{2}|20\d{2})|(?:19\d{2}|20\d{2})[/.-]\d{1,2}[/.-]\d{1,2})"
_NUMERIC_MONTH_YEAR = r"(?:\d{1,2}[/.-](?:19\d{2}|20\d{2})|(?:19\d{2}|20\d{2})[/.-]\d{1,2})"
_TEXTUAL_MONTH_YEAR = rf"(?:(?:\d{{1,2}}\s+)?(?:{MONTH_NAME_PATTERN})\.?\s+(?:19\d{{2}}|20\d{{2}}))"
_YEAR_TOKEN = r"(?:19\d{2}|20\d{2})"
_DATE_TOKEN = rf"(?:{_NUMERIC_DAY_MONTH_YEAR}|{_NUMERIC_MONTH_YEAR}|{_TEXTUAL_MONTH_YEAR}|{_YEAR_TOKEN})"
_CURRENT_DATE_TOKEN = r"(?:present|current|currently|ongoing|now|actuel|actuelle|actuellement|a ce jour|aujourdhui|to date)"
_DATE_RANGE_RE = re.compile(
    rf"(?P<range>(?:de|du|from)?\s*{_DATE_TOKEN}\s*"
    rf"(?:[\u2010-\u2015-]|\b(?:a|au|to|until)\b|\bjusqu(?:a|\s+a)\b)\s*"
    rf"(?:{_DATE_TOKEN}|{_CURRENT_DATE_TOKEN}))",
    flags=re.IGNORECASE,
)
_CURRENT_START_DATE_RE = re.compile(
    rf"(?P<range>(?:depuis|since|a partir de|a compter de)\s+{_DATE_TOKEN})",
    flags=re.IGNORECASE,
)
_DATE_OR_CURRENT_FRAGMENT_RE = re.compile(rf"{_DATE_TOKEN}|{_CURRENT_DATE_TOKEN}", flags=re.IGNORECASE)
_CALENDAR_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_EDUCATION_YEAR_RANGE_RE = re.compile(
    r"\b(?P<start>19\d{2}|20\d{2})"
    r"(?:\s*[\u2010-\u2015-]\s*(?P<end>19\d{2}|20\d{2}|en cours|present|current|ongoing))?\b",
    flags=re.IGNORECASE,
)
_RAW_EXPERIENCE_SECTION_TERMS = {
    "experience",
    "experiences",
    "experience professionnelle",
    "experiences professionnelles",
    "professional experience",
    "work experience",
}
_RAW_PROJECT_SECTION_TERMS = {
    "academic projects",
    "portfolio",
    "personal projects",
    "project portfolio",
    "projects",
    "projets",
    "projets academiques",
    "projets personnels",
    "projets realises",
    "realisation de projets",
    "realisation des projets",
    "realisations",
    "realisations de projets",
    "realisations des projets",
    "selected projects",
}
_RAW_NON_EXPERIENCE_SECTION_TERMS = {
    "certifications",
    "education",
    "education et formation",
    "formation",
    "formations",
    "langues",
    "languages",
    *_RAW_PROJECT_SECTION_TERMS,
}
_RAW_EDUCATION_LINE_MARKERS = (
    "baccalaureat",
    "bachelor",
    "cycle preparatoire",
    "diplome",
    "ecole",
    "faculte",
    "ingenieur d etat",
    "licence",
    "master",
    "universite",
)
_RAW_EDUCATION_DEGREE_MARKERS = (
    "bac",
    "baccalaureat",
    "baccalaureate",
    "bachelor",
    "cycle d ingenierie",
    "cycle preparatoire",
    "diplome",
    "engineering",
    "engineer s degree",
    "ingenieur d etat",
    "licence",
    "master",
    "state engineer",
    "pcsi",
    "psi",
)
_RAW_EDUCATION_REJECT_MARKERS = (
    "certificat",
    "certification",
    "experience",
    "hard skills",
    "internship",
    "langues",
    "languages",
    "projet",
    "project",
    "stage",
)
_RECOVERY_TITLE_REJECT_STARTERS = (
    "and ",
    "built ",
    "created ",
    "designed ",
    "developed ",
    "development ",
    "deployed ",
    "implemented ",
    "improve ",
    "integrate ",
    "integrated ",
    "integration ",
    "participation ",
    "set up ",
    "tools",
    "utilisation ",
    "utilized ",
    "web application ",
)


class CVExtractor:
    def __init__(self, llm_client) -> None:
        self._llm = llm_client

    def extract(self, document: DocumentText) -> StructuredCV:
        with model_call_context(stage="cv_extraction", document_role="cv", document_filename=document.filename):
            raw_payload = self._llm.generate_json(CV_EXTRACTION_PROMPT.format(text=_llm_input_text(document)))
        cv = validate_model(_coerce_cv_payload(raw_payload), StructuredCV)

        # Normalize after validation so downstream matchers see canonical tokens
        # instead of model phrasing. This keeps scoring explainable but ties it
        # to the alias coverage.
        cv.skills.technical = normalize_skill_list(cv.skills.technical)
        cv.skills.tools = normalize_skill_list(cv.skills.tools)
        cv.skills.soft = normalize_skill_list(cv.skills.soft)
        cv.experiences = _merge_recovered_experiences(
            cv.experiences,
            _recover_experiences_from_raw_text(document.text),
        )
        cv.experiences = _drop_non_experience_noise(cv.experiences, document.text)
        cv.experiences = _clear_inconsistent_explicit_duration_dates(cv.experiences)
        all_extracted_experiences = enrich_experience_durations(cv.experiences)
        cv.experience_totals = calculate_cumulative_experience(all_extracted_experiences, cv.declared_total_experience)
        cv.total_experience_months = cv.experience_totals.total_months
        cv.total_experience_years = cv.experience_totals.total_years
        cv.experiences = _prepare_professional_experiences(cv.experiences, document.text)
        # Duration enrichment is derived from extracted dates/durations so the
        # LLM is not trusted to compute experience months directly.
        cv.experiences = enrich_experience_durations(cv.experiences)
        cv.education = _merge_recovered_education(
            cv.education,
            _recover_education_from_raw_text(document.text),
        )
        for education in cv.education:
            education.normalized_level = normalize_education_level(education.normalized_level or education.degree) or ""
        for language in cv.languages:
            language.language = normalize_language(language.language)
            language.normalized_level = normalize_language_level(language.normalized_level)
        enrich_languages_from_raw_text(cv, document.text)
        _enrich_explicit_skills_from_raw_text(cv, document.text)
        if _candidate_name_needs_recovery(cv.candidate_name, document.filename):
            cv.candidate_name = _extract_candidate_name_from_raw_text(document.text) or cv.candidate_name
        cv.raw_text_preview = document.text[:600]
        return cv


def _llm_input_text(document: DocumentText) -> str:
    limit = settings.llm_input_char_limit
    if len(document.text) > limit:
        logger.info(
            "Texte CV tronque avant appel LLM.",
            extra={"filename": document.filename, "char_count": len(document.text), "limit": limit},
        )
    # Truncation protects model cost/latency, but relevant evidence after this
    # limit can be invisible to structured extraction.
    return document.text[:limit]


def _coerce_cv_payload(raw_payload: str | dict) -> dict:
    payload = parse_json_payload(raw_payload) if isinstance(raw_payload, str) else dict(raw_payload)
    payload["declared_total_experience"] = _coerce_scalar(
        payload.get("declared_total_experience") or payload.get("total_experience") or payload.get("years_experience"),
        preferred_keys=("declared_total_experience", "total_experience", "duration", "value", "text"),
    )
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
        experience["declared_duration"] = _coerce_scalar(
            experience.get("declared_duration") or experience.get("duration") or experience.get("duration_text"),
            preferred_keys=("declared_duration", "duration", "value", "text"),
        )
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
        language_value = _coerce_scalar(
            item.get("language") or item.get("name") or item.get("lang"),
            preferred_keys=("language", "name", "value", "text"),
        )
        if not language_value:
            continue
        result.append(
            {
                "language": language_value,
                "normalized_level": _coerce_scalar(
                    item.get("normalized_level") or item.get("level"),
                    preferred_keys=("normalized_level", "level", "name", "value", "text"),
                ),
            }
        )
    return result


def _recover_education_from_raw_text(raw_text: str) -> list[Education]:
    lines = _raw_text_experience_lines(raw_text)
    recovered: list[Education] = []
    for index, line in enumerate(lines):
        if not _looks_like_education_degree_line(line):
            continue
        degree = _clean_education_degree_line(line)
        if not degree:
            continue
        start_year, end_year = _education_years_near(lines, index)
        recovered.append(
            Education(
                degree=degree,
                institution=_recover_education_institution(lines, index),
                start_year=start_year,
                end_year=end_year,
            )
        )
    return recovered


def _looks_like_education_degree_line(line: str) -> bool:
    normalized = normalize_text(line)
    if not normalized or len(normalized) > 130:
        return False
    if normalized in _RAW_NON_EXPERIENCE_SECTION_TERMS or normalized.startswith(("diplome ", "diplomes ")):
        return False
    if any(marker in normalized for marker in _RAW_EDUCATION_REJECT_MARKERS):
        return False
    if re.search(r"\b(i have|j ai|je souhaite|profile|profil)\b", normalized):
        return False
    return any(_starts_with_normalized_term(normalized, marker) for marker in _RAW_EDUCATION_DEGREE_MARKERS)


def _starts_with_normalized_term(normalized_text: str, normalized_term: str) -> bool:
    return bool(re.search(rf"^{re.escape(normalized_term)}(?![a-z0-9])", normalized_text))


def _clean_education_degree_line(line: str) -> str:
    cleaned = _EDUCATION_YEAR_RANGE_RE.sub("", line)
    cleaned = re.split(r"\s+(?:ecole|faculte|universite|lycee)\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" :;,-[]")


def _education_years_near(lines: list[str], index: int) -> tuple[int | None, int | None]:
    offsets = (0, 1, -1, 2, -2, 3, -3)
    for offset in offsets:
        neighbor_index = index + offset
        if not 0 <= neighbor_index < len(lines):
            continue
        parsed = _parse_education_years(lines[neighbor_index])
        if parsed != (None, None):
            return parsed
    return None, None


def _parse_education_years(line: str) -> tuple[int | None, int | None]:
    match = _EDUCATION_YEAR_RANGE_RE.search(normalize_date_text(line))
    if not match:
        return None, None
    start_year = int(match.group("start"))
    raw_end = match.group("end")
    if not raw_end:
        return start_year, start_year
    if raw_end.isdigit():
        return start_year, int(raw_end)
    return start_year, None


def _recover_education_institution(lines: list[str], index: int) -> str | None:
    for neighbor_index in range(index + 1, min(len(lines), index + 3)):
        candidate = lines[neighbor_index]
        normalized = normalize_text(candidate)
        if _parse_education_years(candidate) != (None, None):
            continue
        if _looks_like_education_degree_line(candidate) or _looks_like_raw_experience_section(candidate):
            break
        if any(marker in normalized for marker in _RAW_EDUCATION_REJECT_MARKERS):
            break
        if len(normalized) >= 5:
            return candidate
    return None


def _merge_recovered_education(existing: list[Education], recovered: list[Education]) -> list[Education]:
    merged: list[Education] = []
    for candidate in [*existing, *recovered]:
        duplicate = next((education for education in merged if _is_duplicate_education(education, candidate)), None)
        if duplicate:
            _fill_missing_education_evidence(duplicate, candidate)
            continue
        merged.append(candidate)
    return merged


def _is_duplicate_education(existing: Education, candidate: Education) -> bool:
    existing_degree = normalize_text(existing.degree)
    candidate_degree = normalize_text(candidate.degree)
    if not existing_degree or not candidate_degree:
        return False
    existing_family = _education_degree_family(existing_degree)
    candidate_family = _education_degree_family(candidate_degree)
    if existing_family and candidate_family and existing_family != candidate_family:
        return False
    if existing_degree in candidate_degree or candidate_degree in existing_degree:
        return True
    existing_tokens = {token for token in existing_degree.split() if len(token) > 3}
    candidate_tokens = {token for token in candidate_degree.split() if len(token) > 3}
    shared = existing_tokens & candidate_tokens
    return len(shared) >= min(2, len(candidate_tokens), len(existing_tokens))


def _education_degree_family(normalized_degree: str) -> str | None:
    family_markers = (
        ("master", "master"),
        ("licence", "licence"),
        ("baccalaureat", "bac"),
        ("baccalaureate", "bac"),
        ("bac", "bac"),
        ("bachelor", "bachelor"),
        ("cycle d ingenierie", "engineering"),
        ("ingenieur d etat", "engineering"),
        ("state engineer", "engineering"),
        ("engineer s degree", "engineering"),
        ("engineering", "engineering"),
        ("cycle preparatoire", "preparatory"),
        ("pcsi", "preparatory"),
        ("psi", "preparatory"),
    )
    for marker, family in family_markers:
        if _starts_with_normalized_term(normalized_degree, marker):
            return family
    return None


def _fill_missing_education_evidence(existing: Education, candidate: Education) -> None:
    existing_degree = normalize_text(existing.degree)
    candidate_degree = normalize_text(candidate.degree)
    if existing_degree and candidate_degree and len(existing_degree.split()) <= 2 and len(candidate_degree) > len(existing_degree):
        existing.degree = candidate.degree
    if existing.start_year is None and candidate.start_year is not None:
        existing.start_year = candidate.start_year
    if existing.end_year is None and candidate.end_year is not None:
        existing.end_year = candidate.end_year
    if _education_years_invalid(existing) and candidate.start_year is not None:
        existing.start_year = candidate.start_year
        existing.end_year = candidate.end_year
    if not existing.institution and candidate.institution:
        existing.institution = candidate.institution


def _education_years_invalid(education: Education) -> bool:
    return education.start_year is not None and education.end_year is not None and education.start_year > education.end_year


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
        inferred_level = _infer_language_level_from_window(normalized_text, match)
        # Raw-text inference fills gaps left by the LLM; estimated levels remain
        # weaker evidence than an explicit structured mention.
        if inferred_level and language_rank(inferred_level) > language_rank(language.normalized_level):
            language.normalized_level = inferred_level
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
    requested_skills = normalize_skill_list(
        job.required_skills.mandatory + job.required_skills.preferred
    )
    verified_requested = {
        skill
        for skill in requested_skills
        if _skill_is_explicitly_written(skill, normalized_text)
    }
    # Requested skills that the LLM extracted but the raw CV does not explicitly
    # mention are dropped to reduce prompt-induced false positives.
    technical = _drop_unverified_requested_skills(technical, requested_skills, verified_requested)
    tools = _drop_unverified_requested_skills(tools, requested_skills, verified_requested)
    for experience in cv.experiences:
        experience.skills_used = _drop_unverified_requested_skills(
            experience.skills_used,
            requested_skills,
            verified_requested,
        )
    for project in cv.projects:
        project.skills_used = _drop_unverified_requested_skills(
            project.skills_used,
            requested_skills,
            verified_requested,
        )
    existing = set(normalize_skill_list(technical + tools))
    for skill in sorted(verified_requested):
        if skill in existing:
            continue
        if skill in RAW_TEXT_TOOL_SKILLS:
            tools.append(skill)
        else:
            technical.append(skill)
        existing.add(skill)
    cv.skills.technical = normalize_skill_list(technical)
    cv.skills.tools = normalize_skill_list(tools)
    return cv


def _drop_unverified_requested_skills(
    skills: list[str],
    requested_skills: list[str],
    verified_requested: set[str],
) -> list[str]:
    requested = set(requested_skills)
    return [
        skill
        for skill in normalize_skill_list(skills)
        if skill not in requested or skill in verified_requested
    ]


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
        # Azure AD and similar support contexts should not prove Azure data or
        # cloud platform experience.
        if any(context in window for context in AZURE_NON_DATA_CONTEXTS):
            continue
        return True
    return False


def _recover_experiences_from_raw_text(raw_text: str) -> list[Experience]:
    lines = _raw_text_experience_lines(raw_text)
    line_contexts = _classify_raw_experience_lines(lines)
    recovered: list[Experience] = []
    for index, line in enumerate(lines):
        if _raw_context_blocks_experience(line_contexts[index], line):
            continue
        if _looks_like_raw_non_experience_line(line):
            continue
        normalized_line = normalize_date_text(line)
        date_match = _DATE_RANGE_RE.search(normalized_line) or _CURRENT_START_DATE_RE.search(normalized_line)
        if date_match:
            if _date_line_looks_educational(lines, index):
                continue
            title = _recover_title_for_date_line(lines, line_contexts, index, line, date_match.start())
            if not title:
                continue
            recovered.append(
                Experience(
                    job_title=title,
                    company=_recover_company_for_date_line(lines, line_contexts, index),
                    start_date=date_match.group("range").strip(),
                    missions=_recover_mission_lines(lines, line_contexts, index),
                )
            )
            continue

        if not parse_explicit_duration(line):
            if _looks_like_undated_internship_title_line(line) and not _has_nearby_date(lines, index):
                title = _recover_title_candidate(line)
                if title:
                    recovered.append(
                        Experience(
                            job_title=title,
                            company=_recover_inline_company(line, title),
                            missions=_recover_mission_lines(lines, line_contexts, index),
                        )
                    )
            continue
        title = _recover_title_from_explicit_duration_line(line)
        if not title:
            continue
        recovered.append(
            Experience(
                job_title=title,
                start_date=_first_calendar_year(normalized_line),
                declared_duration=line,
            )
        )
    return recovered


def _raw_text_experience_lines(raw_text: str) -> list[str]:
    return [
        cleaned
        for line in re.split(r"[\n\r]+", raw_text)
        if (cleaned := _clean_raw_experience_line(line))
    ]


def _clean_raw_experience_line(line: str) -> str:
    line = re.sub(r"[\t\u00a0]+", " ", line)
    line = re.sub(r"^[\s*\u2022\u25aa\u25cf\-\u2010-\u2015]+", "", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip(" .")


def _classify_raw_experience_lines(lines: list[str]) -> list[str]:
    contexts: list[str] = []
    current_context = "unknown"
    for line in lines:
        if _looks_like_raw_experience_section(line):
            current_context = "professional_experience"
        elif _looks_like_project_or_portfolio_section(line):
            current_context = "project_or_portfolio"
        elif _looks_like_raw_non_experience_heading(line):
            current_context = "non_experience"
        contexts.append(current_context)
    return contexts


def _raw_context_blocks_experience(context: str, line: str = "") -> bool:
    if context == "project_or_portfolio" and _contains_internship_marker(line):
        return False
    return context in {"project_or_portfolio", "non_experience"}


def _raw_context_breaks_neighbor_search(line_contexts: list[str], index: int, neighbor_index: int) -> bool:
    context = line_contexts[index]
    neighbor_context = line_contexts[neighbor_index]
    return context != "unknown" and neighbor_context != context


def _recover_title_for_date_line(
    lines: list[str],
    line_contexts: list[str],
    index: int,
    line: str,
    date_start: int,
) -> str | None:
    same_line = _recover_title_candidate(line[:date_start])
    if same_line:
        return same_line
    for neighbor_index in range(index - 1, max(-1, index - 9), -1):
        if not 0 <= neighbor_index < len(lines):
            continue
        if (
            _raw_context_breaks_neighbor_search(line_contexts, index, neighbor_index)
            or _raw_context_blocks_experience(line_contexts[neighbor_index], lines[neighbor_index])
            or _line_contains_date_evidence(lines[neighbor_index])
            or _looks_like_raw_non_experience_line(lines[neighbor_index])
            or _looks_like_raw_experience_section(lines[neighbor_index])
        ):
            break
        title = _recover_title_candidate(lines[neighbor_index])
        if title:
            return title
    for neighbor_index in range(index + 1, min(len(lines), index + 4)):
        if not 0 <= neighbor_index < len(lines):
            continue
        if (
            _raw_context_breaks_neighbor_search(line_contexts, index, neighbor_index)
            or _raw_context_blocks_experience(line_contexts[neighbor_index], lines[neighbor_index])
            or _line_contains_date_evidence(lines[neighbor_index])
            or _looks_like_raw_non_experience_line(lines[neighbor_index])
            or _looks_like_raw_experience_section(lines[neighbor_index])
        ):
            break
        title = _recover_title_candidate(lines[neighbor_index])
        if title:
            return title
    return None


def _recover_title_from_explicit_duration_line(line: str) -> str | None:
    title_text = re.split(r"\(\s*\d", line, maxsplit=1)[0]
    if title_text == line:
        title_text = re.split(
            r"\b\d+(?:[.,]\d+)?\s*(?:an|ans|annee|annees|year|years|yr|yrs|mois|month|months|mo)\b",
            line,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
    title_text = _CALENDAR_YEAR_RE.sub("", title_text)
    return _recover_title_candidate(title_text or line)


def _recover_title_candidate(value: str) -> str | None:
    cleaned = _clean_experience_title(re.sub(r"[(\[{]+$", "", value).strip())
    cleaned = _strip_contact_prefix_from_experience_title(cleaned)
    if not cleaned or _looks_like_raw_experience_section(cleaned):
        return None
    normalized = normalize_text(cleaned)
    if any(normalized.startswith(starter) for starter in _RECOVERY_TITLE_REJECT_STARTERS):
        return None
    if _contains_internship_marker(cleaned):
        return cleaned[:80]
    title = _extract_role_title(cleaned)
    return title if _is_professional_experience_title(title) else None


def _strip_contact_prefix_from_experience_title(value: str) -> str:
    cleaned = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b\s*", "", value)
    cleaned = re.sub(r"^(?:linkedin|github)\s*:\s*\S+\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\+?\d[\d\s()./-]{7,}\d\s+", "", cleaned)
    return _clean_experience_title(cleaned)


def _looks_like_raw_experience_section(line: str) -> bool:
    normalized = normalize_text(line)
    if normalized in _RAW_EXPERIENCE_SECTION_TERMS:
        return True
    return bool(
        len(normalized.split()) <= 8
        and re.search(r"\b(?:experience professionnelle|experiences professionnelles|professional experience|work experience)\b", normalized)
    )


def _looks_like_project_or_portfolio_section(line: str) -> bool:
    normalized = normalize_text(line)
    if normalized in {"chef de projet", "project manager"}:
        return False
    if normalized in _RAW_PROJECT_SECTION_TERMS:
        return True
    if len(normalized.split()) > 5:
        return False
    return bool(
        re.match(
            r"^(?:academic |personal |selected )?"
            r"(?:projets?|projects?|portfolio|realisations?)(?:\s+(?:academiques?|personnels?|realises?))?$",
            normalized,
        )
    )


def _looks_like_raw_non_experience_heading(line: str) -> bool:
    if _contains_internship_marker(line):
        return False
    normalized = normalize_text(line)
    return normalized in _RAW_NON_EXPERIENCE_SECTION_TERMS


def _looks_like_raw_non_experience_line(line: str) -> bool:
    if _contains_internship_marker(line):
        return False
    normalized = normalize_text(line)
    return _looks_like_raw_non_experience_heading(line) or any(
        marker in normalized for marker in _RAW_EDUCATION_LINE_MARKERS
    )


def _first_calendar_year(value: str) -> str | None:
    match = _CALENDAR_YEAR_RE.search(value)
    return match.group(1) if match else None


def _recover_company_for_date_line(lines: list[str], line_contexts: list[str], index: int) -> str | None:
    for neighbor_index in (index - 1, index + 1, index - 2):
        if not 0 <= neighbor_index < len(lines):
            continue
        if _raw_context_breaks_neighbor_search(line_contexts, index, neighbor_index) or _raw_context_blocks_experience(
            line_contexts[neighbor_index],
            lines[neighbor_index],
        ):
            continue
        candidate = lines[neighbor_index]
        if _line_contains_date_evidence(candidate) or _recover_title_candidate(candidate):
            continue
        company = _extract_company(candidate, "")
        if company:
            return company
    return None


def _recover_inline_company(line: str, title: str) -> str | None:
    suffix = line.replace(title, "", 1).strip(" ,;:-")
    if not suffix:
        return None
    company = suffix.split(",", maxsplit=1)[0].strip(" ,;:-")
    return company[:80] or None


def _recover_mission_lines(lines: list[str], line_contexts: list[str], index: int) -> list[str]:
    missions: list[str] = []
    for neighbor_index in range(index + 1, min(len(lines), index + 4)):
        if _raw_context_breaks_neighbor_search(line_contexts, index, neighbor_index) or _raw_context_blocks_experience(
            line_contexts[neighbor_index],
            lines[neighbor_index],
        ):
            break
        candidate = lines[neighbor_index]
        if _line_contains_date_evidence(candidate) or _recover_title_candidate(candidate) or _looks_like_raw_experience_section(candidate):
            break
        if _looks_like_raw_non_experience_line(candidate):
            break
        normalized = normalize_text(candidate)
        if len(normalized) >= 20:
            missions.append(candidate)
        if len(missions) == 2:
            break
    return missions


def _looks_like_undated_internship_title_line(line: str) -> bool:
    normalized = normalize_text(line)
    return bool(re.match(r"^(stage|stagiaire|internship|intern|pfe)\b", normalized))


def _has_nearby_date(lines: list[str], index: int) -> bool:
    start = max(0, index - 3)
    end = min(len(lines), index + 6)
    return any(neighbor_index != index and _line_contains_date_evidence(lines[neighbor_index]) for neighbor_index in range(start, end))


def _line_contains_date_evidence(line: str) -> bool:
    normalized = normalize_date_text(line)
    return bool(_DATE_RANGE_RE.search(normalized) or _CURRENT_START_DATE_RE.search(normalized))


def _date_line_looks_educational(lines: list[str], index: int) -> bool:
    line = lines[index]
    normalized = normalize_date_text(line)
    if not re.fullmatch(r"(?:19\d{2}|20\d{2})(?:\s*[\u2010-\u2015-]\s*(?:19\d{2}|20\d{2}|en cours|present|current))?", normalized):
        return False
    return any(
        _looks_like_raw_non_experience_line(lines[neighbor_index])
        for neighbor_index in range(index + 1, min(len(lines), index + 3))
    )


def _merge_recovered_experiences(experiences: list[Experience], recovered: list[Experience]) -> list[Experience]:
    merged = list(experiences)
    for candidate in recovered:
        duplicate = next((existing for existing in merged if _is_duplicate_recovered_experience(existing, candidate)), None)
        if duplicate:
            _fill_missing_duration_evidence(duplicate, candidate)
            continue
        merged.append(candidate)
    return merged


def _drop_non_experience_noise(experiences: list[Experience], raw_text: str = "") -> list[Experience]:
    return [
        experience
        for experience in experiences
        if _looks_like_real_experience(experience) and not _experience_evidence_lives_in_project_section(experience, raw_text)
    ]


def _clear_inconsistent_explicit_duration_dates(experiences: list[Experience]) -> list[Experience]:
    for experience in experiences:
        explicit_months = parse_explicit_duration(_experience_recovery_blob(experience))
        if explicit_months is None:
            continue
        start_year = _single_year_value(experience.start_date)
        end_year = _single_year_value(experience.end_date)
        if start_year is None or end_year is None:
            continue
        year_range_months = (end_year - start_year + 1) * 12
        if year_range_months > explicit_months + 6:
            experience.start_date = None
            experience.end_date = None
    return experiences


def _single_year_value(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*(19\d{2}|20\d{2})\s*", value)
    return int(match.group(1)) if match else None


def _looks_like_real_experience(experience: Experience) -> bool:
    if _looks_like_education_experience(experience):
        return False
    if _looks_like_project_or_portfolio_experience(experience):
        return False
    raw_title = experience.job_title or ""
    raw_context = " ".join([raw_title, experience.declared_duration or ""])
    if _contains_internship_marker(raw_context):
        return True
    if _is_professional_experience_title(_extract_role_title(raw_title)):
        return True
    return _has_duration_evidence(experience)


def _looks_like_project_or_portfolio_experience(experience: Experience) -> bool:
    title = normalize_text(experience.job_title)
    company = normalize_text(experience.company)
    blob = _experience_recovery_blob(experience)
    if _contains_internship_marker(blob):
        return False
    if _looks_like_project_or_portfolio_section(experience.job_title or ""):
        return True
    if company and _looks_like_project_or_portfolio_section(experience.company or ""):
        return True
    if title.startswith(("project manager", "chef de projet")):
        return False
    if not company and re.match(r"^(?:projets?|projects?|portfolio|realisations?|realisation)\b", title):
        return True
    project_context_markers = (
        "academic project",
        "personal project",
        "portfolio",
        "projet academique",
        "projet personnel",
        "realisation de projet",
        "realisation des projets",
    )
    return not company and any(marker in blob for marker in project_context_markers)


def _experience_evidence_lives_in_project_section(experience: Experience, raw_text: str) -> bool:
    if not raw_text:
        return False
    if _contains_internship_marker(_experience_recovery_blob(experience)):
        return False
    lines = _raw_text_experience_lines(raw_text)
    line_contexts = _classify_raw_experience_lines(lines)
    project_hits = 0
    professional_hits = 0
    for line, context in zip(lines, line_contexts, strict=True):
        if not _raw_line_matches_experience_evidence(line, experience):
            continue
        if context == "project_or_portfolio":
            project_hits += 1
        elif context == "professional_experience":
            professional_hits += 1
    return project_hits > 0 and professional_hits == 0


def _raw_line_matches_experience_evidence(line: str, experience: Experience) -> bool:
    normalized_line = normalize_text(line)
    if not normalized_line:
        return False
    title = normalize_text(experience.job_title)
    if title and title in normalized_line:
        return True
    company = normalize_text(experience.company)
    if company and company in normalized_line:
        return True
    date_fragments = _experience_date_fragments(experience)
    line_fragments = {normalize_text(match.group(0)) for match in _DATE_OR_CURRENT_FRAGMENT_RE.finditer(normalize_date_text(line))}
    if date_fragments and len(date_fragments & line_fragments) >= min(2, len(date_fragments)):
        return True
    for mission in experience.missions:
        normalized_mission = normalize_text(mission)
        if normalized_mission and (normalized_mission in normalized_line or normalized_line in normalized_mission):
            return True
    return False


def _looks_like_education_experience(experience: Experience) -> bool:
    company = normalize_text(experience.company)
    if not company or not any(marker in company for marker in ("ecole", "faculte", "lycee", "school", "universite")):
        return False
    title = normalize_text(experience.job_title)
    if not any(
        marker in title
        for marker in (
            "baccalaureat",
            "baccalaureate",
            "ingenieur",
            "ingenieure",
            "licence",
            "master",
            "sciences",
            "telecommunication",
        )
    ):
        return False
    return _experience_dates_are_year_only(experience)


def _experience_dates_are_year_only(experience: Experience) -> bool:
    values = [value for value in (experience.start_date, experience.end_date) if value]
    return bool(values) and all(re.fullmatch(r"\s*(19\d{2}|20\d{2})\s*", value) for value in values)


def _is_duplicate_recovered_experience(existing: Experience, candidate: Experience) -> bool:
    existing_blob = _experience_recovery_blob(existing)
    candidate_source = normalize_text(candidate.declared_duration or candidate.start_date)
    if candidate_source and candidate_source in existing_blob and _has_duration_evidence(existing):
        return True

    existing_title = _experience_duplicate_title(existing.job_title)
    candidate_title = _experience_duplicate_title(candidate.job_title)
    if not _experience_titles_overlap(existing_title, candidate_title):
        return False

    existing_dates = _experience_date_fragments(existing)
    candidate_dates = _experience_date_fragments(candidate)
    if existing_dates and candidate_dates and existing_dates & candidate_dates:
        return True
    if existing_dates and candidate_dates and len(existing_dates & candidate_dates) >= min(2, len(candidate_dates)):
        return True

    existing_duration = parse_explicit_duration(existing_blob)
    candidate_duration = parse_explicit_duration(_experience_recovery_blob(candidate))
    existing_years = set(_CALENDAR_YEAR_RE.findall(existing_blob))
    candidate_years = set(_CALENDAR_YEAR_RE.findall(_experience_recovery_blob(candidate)))
    return bool(
        existing_duration
        and candidate_duration
        and existing_duration == candidate_duration
        and (not existing_years or not candidate_years or bool(existing_years & candidate_years))
    )


def _has_duration_evidence(experience: Experience) -> bool:
    return bool(
        experience.start_date
        or experience.end_date
        or experience.declared_duration
        or parse_explicit_duration(_experience_recovery_blob(experience))
    )


def _fill_missing_duration_evidence(existing: Experience, candidate: Experience) -> None:
    if candidate.start_date and (not existing.start_date or (not existing.end_date and len(_experience_date_fragments(candidate)) > len(_experience_date_fragments(existing)))):
        existing.start_date = candidate.start_date
        existing.end_date = candidate.end_date
    if candidate.declared_duration and not parse_explicit_duration(_experience_recovery_blob(existing)):
        existing.declared_duration = candidate.declared_duration
    if candidate.company and not existing.company:
        existing.company = candidate.company
    if candidate.missions:
        existing.missions = _merge_text_list(existing.missions, candidate.missions)


def _merge_text_list(existing: list[str], candidates: list[str]) -> list[str]:
    merged = list(existing)
    seen = {normalize_text(item) for item in merged}
    for candidate in candidates:
        key = normalize_text(candidate)
        if key and key not in seen:
            merged.append(candidate)
            seen.add(key)
    return merged


def _experience_recovery_blob(experience: Experience) -> str:
    return normalize_text(
        " ".join(
            item
            for item in [
                experience.job_title or "",
                experience.company or "",
                experience.start_date or "",
                experience.end_date or "",
                experience.declared_duration or "",
                " ".join(experience.missions),
            ]
            if item
        )
    )


def _experience_date_fragments(experience: Experience) -> set[str]:
    date_text = normalize_date_text(
        " ".join(
            item
            for item in [experience.start_date or "", experience.end_date or "", experience.declared_duration or ""]
            if item
        )
    )
    return {normalize_text(match.group(0)) for match in _DATE_OR_CURRENT_FRAGMENT_RE.finditer(date_text)}


def _experience_duplicate_title(value: str | None) -> str:
    normalized = normalize_text(_clean_experience_title(value or ""))
    normalized = re.sub(
        r"^(?:stage|stagiaire|internship|intern|pfe|alternance)\b"
        r"(?:\s+(?:de|d|a|en|fin|final|year|study|etude|master|bachelor))*\s*",
        "",
        normalized,
    )
    role_title = _extract_role_title(normalized)
    return normalize_text(role_title or normalized)


def _experience_titles_overlap(first: str, second: str) -> bool:
    if not first or not second:
        return False
    if first in second or second in first:
        return True
    first_tokens = {token for token in first.split() if len(token) > 2}
    second_tokens = {token for token in second.split() if len(token) > 2}
    return len(first_tokens & second_tokens) >= 2


def _prepare_professional_experiences(experiences: list[Experience], raw_text: str) -> list[Experience]:
    prepared: list[Experience] = []
    for experience in experiences:
        raw_title = experience.job_title or ""
        raw_duration = experience.declared_duration or ""
        raw_context = " ".join([raw_title, raw_duration, " ".join(experience.missions)])
        if _is_internship_experience(experience, raw_context, raw_text):
            continue
        if _has_current_experience_marker(experience, raw_context, raw_text):
            experience.end_date = "Present"
        experience.job_title = _extract_role_title(raw_title)
        if not _is_professional_experience_title(experience.job_title or ""):
            continue
        # Company recovery is heuristic and intentionally conservative; it
        # uses known companies or "chez/at" patterns rather than inventing.
        experience.company = experience.company or _extract_company(
            " ".join([experience.job_title or "", " ".join(experience.missions)]),
            " ".join(experience.missions),
        )
        experience.skills_used = normalize_skill_list(experience.skills_used)
        prepared.append(experience)
    return prepared


def _is_internship_experience(experience: Experience, raw_context: str, raw_text: str) -> bool:
    if _contains_internship_marker(raw_context):
        return True
    date_context = _experience_date_context(experience, raw_text)
    return _internship_marker_applies_to_experience(experience, date_context)


def _contains_internship_marker(value: str) -> bool:
    return bool(INTERNSHIP_MARKER_RE.search(normalize_text(value)))


def _internship_marker_applies_to_experience(experience: Experience, date_context: str) -> bool:
    normalized_context = normalize_text(date_context)
    if not INTERNSHIP_MARKER_RE.search(normalized_context):
        return False
    title = normalize_text(_extract_role_title(experience.job_title or ""))
    if not title:
        return True
    title_tokens = {token for token in title.split() if len(token) > 2}
    for match in INTERNSHIP_MARKER_RE.finditer(normalized_context):
        window = normalized_context[max(0, match.start() - 80): match.end() + 80]
        window_tokens = {token for token in window.split() if len(token) > 2}
        if title in window or len(title_tokens & window_tokens) >= min(2, len(title_tokens)):
            return True
    return False


def _has_current_experience_marker(experience: Experience, raw_context: str, raw_text: str) -> bool:
    if experience.end_date:
        return False
    if has_current_start_marker(experience.start_date) or has_current_start_marker(raw_context):
        return True
    return _raw_start_date_has_current_marker(raw_text, experience.start_date)


def _raw_start_date_has_current_marker(raw_text: str, start_date: str | None) -> bool:
    if not start_date:
        return False
    normalized_text = normalize_text(raw_text)
    normalized_start = normalize_text(start_date)
    if not normalized_start:
        return False
    start_index = normalized_text.find(normalized_start)
    if start_index < 0:
        return False
    before = normalized_text[max(0, start_index - 35):start_index]
    return bool(re.search(r"\b(depuis|since|a partir de|a compter de)\b", before))


def _experience_date_window(experience: Experience, raw_text: str) -> str:
    normalized_text = normalize_text(raw_text)
    for value in (experience.start_date, experience.end_date):
        normalized_value = normalize_text(value)
        if not normalized_value:
            continue
        index = normalized_text.find(normalized_value)
        if index >= 0:
            return normalized_text[max(0, index - 100): index + len(normalized_value) + 45]
    return ""


def _experience_date_context(experience: Experience, raw_text: str) -> str:
    return _experience_date_line_context(experience, raw_text) or _experience_date_window(experience, raw_text)


def _experience_date_line_context(experience: Experience, raw_text: str) -> str:
    lines = [normalize_text(line) for line in re.split(r"[\n\r]+", raw_text) if normalize_text(line)]
    for value in (experience.start_date, experience.end_date):
        normalized_value = normalize_text(value)
        if not normalized_value:
            continue
        for index, line in enumerate(lines):
            if normalized_value in line:
                start = max(0, index - 1)
                end = min(len(lines), index + 2)
                return " ".join(lines[start:end])
    return ""


def _clean_experience_title(value: str) -> str:
    value = re.sub(r"^[\u2022\-\u2013\u2014*\s]+", "", value)
    value = re.sub(r"^[.:,;|/\\\s]+", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" :;-,()[]|")


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
    # Filtering protects scoring from education/project fragments being counted
    # as professional experience, but role-marker coverage should be tested
    # across non-Data/BI resumes too.
    return any(marker in normalized for marker in role_markers)

# Role dans le projet:
# Ce fichier transforme un CV texte en StructuredCV. Il combine LLM, coercition, normalisation, enrichissements raw-text et durees.
