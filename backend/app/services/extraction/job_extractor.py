from __future__ import annotations

import logging
import re

from app.config import settings
from app.core.model_audit import model_call_context
from app.schemas.document import DocumentText
from app.schemas.job import LanguageRequirement, StructuredJobDescription
from app.services.extraction.coercion import (
    coerce_int as _coerce_int,
)
from app.services.extraction.coercion import (
    coerce_scalar as _coerce_scalar,
)
from app.services.extraction.coercion import (
    coerce_string_list as _coerce_string_list,
)
from app.services.extraction.output_validator import parse_json_payload, validate_model
from app.services.extraction.prompts import JOB_EXTRACTION_PROMPT
from app.services.normalization.education_normalizer import normalize_education_level
from app.services.normalization.language_normalizer import normalize_language, normalize_language_level
from app.services.normalization.skill_normalizer import normalize_skill_list
from app.services.normalization.text_normalizer import dedupe_by_normalized_key, normalize_text
from app.services.rules.domain_rules import get_domain_rule_section

logger = logging.getLogger(__name__)

_JOB_RULES = get_domain_rule_section("job")


def _job_rule_list(name: str) -> list[str]:
    value = _JOB_RULES.get(name, [])
    return [str(item) for item in value] if isinstance(value, list) else []


def _job_rule_map(name: str) -> dict[str, str]:
    value = _JOB_RULES.get(name, {})
    if not isinstance(value, dict):
        return {}
    return {str(key): str(mapped) for key, mapped in value.items()}


def _technical_text_rules() -> dict[str, tuple[str, tuple[str, ...]]]:
    value = _JOB_RULES.get("technical_text_rules", {})
    if not isinstance(value, dict):
        return {}
    rules: dict[str, tuple[str, tuple[str, ...]]] = {}
    for skill, rule in value.items():
        if not isinstance(rule, dict):
            continue
        hints = rule.get("hints", [])
        if isinstance(hints, list):
            rules[str(skill)] = (str(rule.get("bucket", "preferred")), tuple(str(item) for item in hints))
    return rules


class JobExtractor:
    def __init__(self, llm_client) -> None:
        self._llm = llm_client

    def extract(self, document: DocumentText) -> StructuredJobDescription:
        with model_call_context(stage="job_extraction", document_role="job", document_filename=document.filename):
            raw_payload = self._llm.generate_json(JOB_EXTRACTION_PROMPT.format(text=_llm_input_text(document)))
        job = validate_model(_coerce_job_payload(raw_payload), StructuredJobDescription)

        # The model output is normalized and then reconciled with raw text so
        # scoring is based on explicit evidence instead of model-only wording.
        job.required_skills.mandatory = normalize_skill_list(job.required_skills.mandatory)
        job.required_skills.preferred = normalize_skill_list(job.required_skills.preferred)
        job.required_skills.soft = normalize_skill_list(job.required_skills.soft)
        _apply_job_text_rules(job, document.text)
        job.experience_requirements.required_domains = _clean_required_domains(
            document.text,
            job.experience_requirements.required_domains,
        )
        job.education_requirements.minimum_level = normalize_education_level(job.education_requirements.minimum_level) or ""
        for language in job.language_requirements:
            language.language = normalize_language(language.language)
            language.minimum_level = normalize_language_level(language.minimum_level)
        job.responsibilities = _clean_responsibilities(document.text, job.responsibilities)
        job.raw_text_preview = document.text[:600]
        return job


def _llm_input_text(document: DocumentText) -> str:
    limit = settings.llm_input_char_limit
    if len(document.text) > limit:
        logger.info(
            "Texte fiche de poste tronque avant appel LLM.",
            extra={"filename": document.filename, "char_count": len(document.text), "limit": limit},
        )
    # The same LLM limit is used for jobs and CVs; truncation can hide late
    # requirements, so audit logs keep the original length.
    return document.text[:limit]


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
        language_value = _coerce_scalar(
            item.get("language") or item.get("name") or item.get("lang"),
            preferred_keys=("language", "name", "value", "text"),
        )
        if language_value:
            result.append(
                {
                    "language": language_value,
                    "minimum_level": _coerce_scalar(
                        item.get("minimum_level") or item.get("level"),
                        preferred_keys=("minimum_level", "level", "name", "value", "text"),
                    ),
                }
            )
    return result


LANGUAGE_SKILLS = set(_job_rule_list("language_skills"))
LANGUAGE_TOKEN_MAP = _job_rule_map("language_token_map")
LANGUAGE_LEVEL_TERMS = set(_job_rule_list("language_level_terms"))
SOFT_SKILL_TERMS = tuple(_job_rule_list("soft_skill_terms"))
TECHNICAL_TEXT_RULES = _technical_text_rules()
DOMAIN_REQUIREMENT_SIGNALS = (
    "required domain",
    "domain required",
    "required industry",
    "industry required",
    "domaine requis",
    "domaines requis",
    "secteur requis",
    "secteurs requis",
    "experience requise dans le domaine",
    "experience obligatoire dans le domaine",
    "experience requise dans le secteur",
    "experience obligatoire dans le secteur",
    "connaissance obligatoire du secteur",
)


def _apply_job_text_rules(job: StructuredJobDescription, text: str) -> None:
    normalized = normalize_text(text)
    if not job.job_title:
        job.job_title = _infer_job_title(text)

    # Skills are re-bucketed from raw text to prevent languages and soft skills
    # from inflating the technical score. The rule set is explicit, so its
    # vocabulary balance should be audited across job families.
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
        if any(_contains_technical_signal(normalized, signal) for signal in signals):
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


def _clean_required_domains(text: str, domains: list[str]) -> list[str]:
    normalized_text = normalize_text(text)
    # Domains are only kept when the job text explicitly frames them as required;
    # otherwise generic industry mentions would over-penalize candidates.
    if not domains or not _has_explicit_domain_requirement(normalized_text):
        return []
    kept: list[str] = []
    for domain in domains:
        normalized_domain = normalize_text(domain)
        if normalized_domain and normalized_domain in normalized_text and normalized_domain not in kept:
            kept.append(normalized_domain)
    return kept


def _has_explicit_domain_requirement(normalized_text: str) -> bool:
    return any(signal in normalized_text for signal in DOMAIN_REQUIREMENT_SIGNALS)


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
    if _contains_technical_signal(normalized_text, skill):
        return True
    for canonical, (_, signals) in TECHNICAL_TEXT_RULES.items():
        if skill == canonical:
            return any(_contains_technical_signal(normalized_text, signal) for signal in signals)
    return False


def _contains_technical_signal(normalized_text: str, signal: str) -> bool:
    normalized_signal = normalize_text(signal)
    if not normalized_signal:
        return False
    return re.search(
        rf"(?<![a-z0-9+#]){re.escape(normalized_signal)}(?![a-z0-9+#])",
        normalized_text,
    ) is not None


def _add_language_requirements(job: StructuredJobDescription, languages: list[str], normalized_text: str) -> None:
    if "french" in normalized_text or "francais" in normalized_text:
        languages.append("french")
    if "english" in normalized_text or "anglais" in normalized_text:
        languages.append("english")
    inferred_levels = _infer_language_requirement_levels(normalized_text)
    existing = {normalize_language(language.language): language for language in job.language_requirements}
    for normalized, requirement in existing.items():
        if normalized and not requirement.minimum_level and normalized in inferred_levels:
            requirement.minimum_level = inferred_levels[normalized]
    for language in languages:
        normalized = normalize_language(language)
        if normalized and normalized not in existing:
            job.language_requirements.append(
                LanguageRequirement(language=normalized, minimum_level=inferred_levels.get(normalized))
            )
            existing[normalized] = job.language_requirements[-1]


def _infer_language_requirement_levels(normalized_text: str) -> dict[str, str]:
    tokens = normalized_text.split()
    level_terms = {normalize_language_level(term) or term for term in LANGUAGE_LEVEL_TERMS}
    levels_by_language: dict[str, tuple[str, int]] = {}
    for index, token in enumerate(tokens):
        language = normalize_language(LANGUAGE_TOKEN_MAP.get(token, token))
        if language not in {"francais", "anglais", "arabe"}:
            continue
        candidates: list[tuple[int, str]] = []
        for level_index in range(max(0, index - 4), min(len(tokens), index + 5)):
            level = normalize_language_level(tokens[level_index])
            if level and level in level_terms:
                candidates.append((abs(index - level_index), level))
        if not candidates:
            continue
        distance, level = sorted(candidates, key=lambda item: (item[0], item[1]))[0]
        current = levels_by_language.get(language)
        if current is None or distance < current[1]:
            levels_by_language[language] = (level, distance)
    return {language: level for language, (level, _) in levels_by_language.items()}


def _infer_job_title(text: str) -> str | None:
    for raw_line in text.splitlines():
        line = raw_line.strip(" \t:-")
        normalized = normalize_text(line)
        if not normalized or normalized.startswith("sensitivity"):
            continue
        if normalized.startswith(("mission", "tools", "skills", "competences")):
            return None
        title_signals = (
            "analyst",
            "data analyst",
            "developpeur",
            "developer",
            "engineer",
            "ingenieur",
            "consultant",
            "frontend",
            "backend",
            "full stack",
            "fullstack",
            "software",
            "support",
            "chef de projet",
            "project manager",
            "mobile",
        )
        if any(signal in normalized for signal in title_signals):
            return line
    return None


def _clean_responsibilities(text: str, extracted: list[str]) -> list[str]:
    normalized = normalize_text(text)
    responsibilities: list[str] = []
    # These deterministic responsibility templates make Data/BI postings more
    # stable, but they are not a semantic parser and may under-cover other roles.
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
        return dedupe_by_normalized_key(responsibilities)
    return dedupe_by_normalized_key([item for item in extracted if _looks_like_responsibility(item)])


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

# Role dans le projet:
# Ce fichier transforme une fiche de poste en StructuredJobDescription. Il normalise les criteres et applique des regles textuelles explicites.
