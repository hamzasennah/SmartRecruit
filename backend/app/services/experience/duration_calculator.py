from __future__ import annotations

import re
from datetime import date

from app.schemas.cv import Experience
from app.schemas.experience import ExperienceDuration, ExperiencePeriod
from app.services.normalization.date_normalizer import (
    calculate_months,
    has_current_start_marker,
    parse_month_year,
)
from app.services.normalization.text_normalizer import normalize_text


MAX_SINGLE_EXPERIENCE_MONTHS = 600


def parse_explicit_duration(text: str | None) -> int | None:
    normalized = normalize_text(text)
    years_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:an|ans|annee|annees|year|years)", normalized)
    months_match = re.search(r"(\d+)\s*(?:mois|month|months)", normalized)
    if not years_match and not months_match:
        return None
    years = float(years_match.group(1).replace(",", ".")) if years_match else 0.0
    months = int(months_match.group(1)) if months_match else 0
    return round(years * 12 + months)


def calculate_experience_duration(
    start_raw: str | None,
    end_raw: str | None,
    declared_duration: str | None = None,
    today: date | None = None,
) -> ExperienceDuration:
    today = today or date.today()
    start_raw, end_raw, single_field_range = _coerce_range(start_raw, end_raw)
    start_date, start_precision = parse_month_year(start_raw, today=today)
    end_date, end_precision = parse_month_year(end_raw, today=today)
    current_marker = has_current_start_marker(start_raw)

    if start_date and not end_date and current_marker:
        end_date = date(today.year, today.month, 1)
        end_precision = "present"

    if start_date and end_date:
        start_date, end_date = _adjust_partial_dates(start_date, start_precision, end_date, end_precision)
        try:
            duration = calculate_months(start_date, end_date)
        except ValueError as error:
            return ExperienceDuration(
                start_date=start_date.strftime("%Y-%m"),
                end_date=end_date.strftime("%Y-%m"),
                start_precision=start_precision,
                end_precision=end_precision,
                calculation_source="date_range",
                confidence=0.0,
                error=str(error),
            )
        plausibility_error = _plausibility_error(duration)
        estimated = "year" in {start_precision, end_precision}
        source = "date_range_single_field" if single_field_range else "date_range"
        if current_marker and end_raw is None:
            source = "date_range_current_marker"
        if plausibility_error:
            return ExperienceDuration(
                start_date=start_date.strftime("%Y-%m"),
                end_date=end_date.strftime("%Y-%m"),
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
            start_precision=start_precision,
            end_precision=end_precision,
            calculation_source=source,
            confidence=confidence,
            estimated=estimated,
        )

    declared = parse_explicit_duration(declared_duration)
    if declared is not None:
        plausibility_error = _plausibility_error(declared)
        if plausibility_error:
            return ExperienceDuration(
                calculation_source="explicit_duration",
                confidence=0.0,
                error=plausibility_error,
            )
        return ExperienceDuration(
            duration_months=declared,
            duration_years=round(declared / 12, 2),
            calculation_source="explicit_duration",
            confidence=0.75,
        )

    return ExperienceDuration(error="Impossible d'interpreter les dates ou la duree declaree.")


def enrich_experience_durations(experiences: list[Experience], today: date | None = None) -> list[Experience]:
    for experience in experiences:
        duration = calculate_experience_duration(
            experience.start_date,
            experience.end_date,
            experience.declared_duration,
            today=today,
        )
        experience.duration = duration
        experience.duration_months = duration.duration_months
    return experiences


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


def _coerce_range(start_raw: str | None, end_raw: str | None) -> tuple[str | None, str | None, bool]:
    if end_raw or not start_raw:
        return start_raw, end_raw, False
    split = _split_date_range(start_raw)
    if not split:
        return start_raw, end_raw, False
    return split[0], split[1], True


def _split_date_range(value: str) -> tuple[str, str] | None:
    separators = (
        r"\s+[–—-]\s+",
        r"\s+(?:a|à|au|to|until|jusqu['’]?a|jusqu\s+a)\s+",
    )
    for separator in separators:
        parts = re.split(separator, value, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            return parts[0].strip(), parts[1].strip()
    return None


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
