from __future__ import annotations

import re
from datetime import date

from app.schemas.cv import Experience
from app.schemas.experience import ExperienceDuration, ExperienceDurationTrace, ExperiencePeriod, ExperienceTotals
from app.services.experience.overlap_manager import calculate_total_unique_months, parse_period_value
from app.services.normalization.date_normalizer import (
    calculate_months,
    has_current_start_marker,
    parse_month_year,
)
from app.services.normalization.text_normalizer import normalize_text

MAX_SINGLE_EXPERIENCE_MONTHS = 600
OVERLAP_POLICY_UNION = "union"
DURATION_UNIT_YEARS = r"an|ans|annee|annees|year|years|yr|yrs"
DURATION_UNIT_MONTHS = r"mois|month|months|mo"
DURATION_PATTERN = re.compile(
    rf"(?:(?P<years>\d+(?:[.,]\d+)?)\s*(?:{DURATION_UNIT_YEARS})\s*(?:et|and)?\s*)?"
    rf"(?P<months>\d+)\s*(?:{DURATION_UNIT_MONTHS})"
    rf"|(?P<years_only>\d+(?:[.,]\d+)?)\s*(?:{DURATION_UNIT_YEARS})"
)


def parse_explicit_duration(text: str | None) -> int | None:
    durations = parse_explicit_durations(text)
    return sum(durations) if durations else None


def parse_explicit_durations(text: str | None) -> list[int]:
    normalized = normalize_text(text)
    durations: list[int] = []
    for match in DURATION_PATTERN.finditer(normalized):
        years_text = match.group("years") or match.group("years_only")
        months_text = match.group("months")
        years = float(years_text.replace(",", ".")) if years_text else 0.0
        months = int(months_text) if months_text else 0
        duration = round(years * 12 + months)
        if duration > 0:
            durations.append(duration)
    return durations


def calculate_experience_duration(
    start_raw: str | None,
    end_raw: str | None,
    declared_duration: str | None = None,
    today: date | None = None,
    entry_text: str | None = None,
) -> ExperienceDuration:
    today = today or date.today()
    original_start_raw = start_raw
    original_end_raw = end_raw
    start_raw, end_raw, single_field_range = _coerce_range(start_raw, end_raw)
    fallback_text = entry_text or " ".join(item for item in [start_raw or "", end_raw or ""] if item)
    source_text = _duration_source_text(entry_text, original_start_raw, original_end_raw)
    declared, declared_source, declared_source_text = _explicit_duration_from_sources(declared_duration, fallback_text)
    start_date, start_precision = parse_month_year(start_raw, today=today)
    end_date, end_precision = parse_month_year(end_raw, today=today)
    current_marker = has_current_start_marker(start_raw) or _contains_current_start_marker(fallback_text)

    if start_date and not end_date and current_marker:
        end_date = date(today.year, today.month, 1)
        end_precision = "present"

    if start_date and end_date:
        start_date, end_date = _adjust_partial_dates(start_date, start_precision, end_date, end_precision)
        try:
            duration = calculate_months(start_date, end_date)
        except ValueError as error:
            if declared is not None:
                return _explicit_duration_result(declared, declared_source, declared_source_text)
            return ExperienceDuration(
                start_date=start_date.strftime("%Y-%m"),
                end_date=end_date.strftime("%Y-%m"),
                source_text=source_text,
                start_precision=start_precision,
                end_precision=end_precision,
                calculation_source="date_range",
                confidence=0.0,
                error=str(error),
            )
        if declared is not None and "year" in {start_precision, end_precision}:
            return _explicit_duration_result(declared, declared_source, declared_source_text)
        plausibility_error = _plausibility_error(duration)
        estimated = "year" in {start_precision, end_precision}
        source = "date_range_single_field" if single_field_range else "date_range"
        if current_marker and end_raw is None:
            source = "date_range_current_marker"
        if plausibility_error:
            return ExperienceDuration(
                start_date=start_date.strftime("%Y-%m"),
                end_date=end_date.strftime("%Y-%m"),
                source_text=source_text,
                start_precision=start_precision,
                end_precision=end_precision,
                calculation_source=source,
                confidence=0.0,
                estimated=estimated,
                error=plausibility_error,
            )
        confidence = _confidence(start_precision, end_precision)
        return ExperienceDuration(
            start_date=start_date.strftime("%Y-%m"),
            end_date=end_date.strftime("%Y-%m"),
            duration_months=duration,
            duration_years=round(duration / 12, 2),
            source_text=source_text,
            start_precision=start_precision,
            end_precision=end_precision,
            calculation_source=source,
            confidence=confidence,
            estimated=estimated,
        )

    if declared is not None:
        return _explicit_duration_result(declared, declared_source, declared_source_text)

    return ExperienceDuration(source_text=source_text, error="Impossible d'interpreter les dates ou la duree declaree.")


def _explicit_duration_from_sources(declared_duration: str | None, entry_text: str | None) -> tuple[int | None, str, str | None]:
    declared = parse_explicit_duration(declared_duration)
    if declared is not None:
        return declared, "explicit_duration", _truncate_source_text(declared_duration)
    return parse_explicit_duration(entry_text), "explicit_duration_entry_text", _truncate_source_text(entry_text)


def _explicit_duration_result(duration_months: int, source: str, source_text: str | None) -> ExperienceDuration:
    plausibility_error = _plausibility_error(duration_months)
    if plausibility_error:
        return ExperienceDuration(
            source_text=source_text,
            calculation_source=source,
            confidence=0.0,
            error=plausibility_error,
        )
    return ExperienceDuration(
        duration_months=duration_months,
        duration_years=round(duration_months / 12, 2),
        source_text=source_text,
        calculation_source=source,
        confidence=0.75 if source == "explicit_duration" else 0.70,
    )


def enrich_experience_durations(experiences: list[Experience], today: date | None = None) -> list[Experience]:
    for experience in experiences:
        duration = calculate_experience_duration(
            experience.start_date,
            experience.end_date,
            experience.declared_duration,
            today=today,
            entry_text=_experience_entry_text(experience),
        )
        experience.duration = duration
        experience.duration_months = duration.duration_months
    return experiences


def calculate_cumulative_experience(
    experiences: list[Experience],
    declared_total_experience: str | None = None,
    overlap_policy: str = OVERLAP_POLICY_UNION,
) -> ExperienceTotals:
    if overlap_policy != OVERLAP_POLICY_UNION:
        raise ValueError("Seule la politique d'union des periodes est supportee.")

    periods: list[tuple[date, date]] = []
    explicit_duration_months = 0
    explicit_duration_count = 0
    entries: list[ExperienceDurationTrace] = []
    for experience in experiences:
        period = experience_to_period(experience)
        if period:
            periods.append((parse_period_value(period.start_date), parse_period_value(period.end_date)))
            entries.append(_experience_duration_trace(experience, counted=True))
            continue
        if experience.duration_months:
            explicit_duration_months += experience.duration_months
            explicit_duration_count += 1
            entries.append(_experience_duration_trace(experience, counted=True))
        else:
            entries.append(_experience_duration_trace(experience, counted=False))

    dated_months = calculate_total_unique_months(periods)
    itemized_total = dated_months + explicit_duration_months
    declared_total_months = parse_explicit_duration(declared_total_experience)
    if itemized_total > 0:
        total_months = itemized_total
        source = "itemized_experiences"
        status = "calculated"
        failure_reason = None
    elif declared_total_months is not None:
        total_months = declared_total_months
        source = "declared_total_experience"
        status = "calculated"
        failure_reason = None
    else:
        total_months = 0
        source = "none"
        status = "not_calculable" if entries else "not_available"
        failure_reason = (
            "Des experiences ont ete extraites, mais aucune date ou duree exploitable n'a permis un calcul."
            if entries
            else "Aucune experience professionnelle exploitable n'a ete detectee."
        )

    return ExperienceTotals(
        total_months=total_months,
        total_years=round(total_months / 12, 2),
        calculated_total_months=total_months if status == "calculated" else None,
        dated_months=dated_months,
        explicit_duration_months=explicit_duration_months,
        declared_total_months=declared_total_months,
        period_count=len(periods),
        explicit_duration_count=explicit_duration_count,
        overlap_policy=overlap_policy,
        calculation_source=source,
        calculation_status=status,
        failure_reason=failure_reason,
        entries=entries,
    )


def experience_to_period(experience: Experience) -> ExperiencePeriod | None:
    duration = experience.duration
    if not duration or not duration.start_date or not duration.end_date or duration.duration_months is None:
        return None
    return ExperiencePeriod(
        start_date=duration.start_date,
        end_date=duration.end_date,
        duration_months=duration.duration_months,
        confidence=duration.confidence,
    )


def _experience_duration_trace(experience: Experience, counted: bool) -> ExperienceDurationTrace:
    duration = experience.duration
    return ExperienceDurationTrace(
        job_title=experience.job_title,
        company=experience.company,
        start_date_raw=experience.start_date,
        end_date_raw=experience.end_date,
        declared_duration=experience.declared_duration,
        start_date=duration.start_date if duration else None,
        end_date=duration.end_date if duration else None,
        duration_months=experience.duration_months,
        calculation_source=duration.calculation_source if duration else "unknown",
        source_text=duration.source_text if duration else None,
        counted_in_total=counted,
        error=duration.error if duration else None,
    )


def _coerce_range(start_raw: str | None, end_raw: str | None) -> tuple[str | None, str | None, bool]:
    if end_raw or not start_raw:
        return start_raw, end_raw, False
    split = _split_date_range(start_raw)
    if not split:
        return start_raw, end_raw, False
    return split[0], split[1], True


def _split_date_range(value: str) -> tuple[str, str] | None:
    compact = _split_compact_ascii_range(value)
    if compact:
        return compact
    separators = (
        r"\s+(?:\ba\b|\b\u00e0\b|\bau\b|\bto\b|\buntil\b|"
        r"\bjusqu(?:'|\u2019)?(?:a|\u00e0)\b|\bjusqu\s+(?:a|\u00e0)\b)\s+",
        r"\s*[\u2010-\u2015]\s*",
        r"\s+-\s+",
        r"(?<=\d{4})\s*-\s*(?=(?:19\d{2}|20\d{2}|present|current|currently|ongoing|now|actuel|actuelle|actuellement)\b)",
    )
    for separator in separators:
        parts = re.split(separator, value, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            return parts[0].strip(), parts[1].strip()
    return None


def _split_compact_ascii_range(value: str) -> tuple[str, str] | None:
    current = r"present|current|currently|ongoing|now|actuel|actuelle|actuellement"
    patterns = (
        rf"^\s*((?:0?[1-9]|1[0-2])[/.-](?:19\d{{2}}|20\d{{2}}))\s*-\s*((?:0?[1-9]|1[0-2])[/.-](?:19\d{{2}}|20\d{{2}})|{current})\s*$",
        rf"^\s*((?:19\d{{2}}|20\d{{2}}))\s*-\s*((?:19\d{{2}}|20\d{{2}})|{current})\s*$",
    )
    for pattern in patterns:
        match = re.match(pattern, value, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    return None


def _experience_entry_text(experience: Experience) -> str:
    return " ".join(
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


def _duration_source_text(entry_text: str | None, start_raw: str | None, end_raw: str | None) -> str | None:
    if entry_text:
        return _truncate_source_text(entry_text)
    joined = " ".join(item for item in [start_raw or "", end_raw or ""] if item)
    return _truncate_source_text(joined)


def _truncate_source_text(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"\s+", " ", value).strip()
    return value[:300] if value else None


def _contains_current_start_marker(value: str | None) -> bool:
    normalized = normalize_text(value)
    return bool(normalized and re.search(r"\b(depuis|since|a partir de|a compter de)\b", normalized))


def _adjust_partial_dates(
    start_date: date,
    start_precision: str,
    end_date: date,
    end_precision: str,
) -> tuple[date, date]:
    if start_precision == "year":
        start_date = date(start_date.year, 1, 1)
    if end_precision == "year":
        end_date = date(end_date.year, 12, 1)
    return start_date, end_date


def _confidence(start_precision: str, end_precision: str) -> float:
    if "year" in {start_precision, end_precision}:
        return 0.60
    if start_precision in {"day", "month"} and end_precision in {"day", "month", "present"}:
        return 0.95
    return 0.75


def _plausibility_error(duration_months: int) -> str | None:
    if duration_months < 0:
        return "Duree d'experience negative."
    if duration_months > MAX_SINGLE_EXPERIENCE_MONTHS:
        return f"Duree d'experience non plausible: {duration_months} mois."
    return None


# Role dans le projet:
# Ce fichier calcule les durees d'experience a partir de dates ou durees declarees. Le CVExtractor l'utilise avant le matching d'experience.
