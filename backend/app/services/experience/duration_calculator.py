from __future__ import annotations

import re
from datetime import date

from app.schemas.cv import Experience
from app.schemas.experience import ExperienceDuration, ExperiencePeriod
from app.services.normalization.date_normalizer import calculate_months, parse_month_year
from app.services.normalization.text_normalizer import normalize_text


def parse_explicit_duration(text: str | None) -> int | None:
    normalized = normalize_text(text)
    years_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:an|ans|annee|annees|year|years)", normalized)
    months_match = re.search(r"(\d+)\s*(?:mois|month|months)", normalized)
    if not years_match and not months_match:
        return None
    years = float(years_match.group(1).replace(",", ".")) if years_match else 0.0
    months = int(months_match.group(1)) if months_match else 0
    return round(years * 12 + months)


def calculate_experience_duration(start_raw: str | None, end_raw: str | None, declared_duration: str | None = None, today: date | None = None) -> ExperienceDuration:
    start_date, start_precision = parse_month_year(start_raw, today=today)
    end_date, end_precision = parse_month_year(end_raw, today=today)
    if start_date and end_date:
        try:
            duration = calculate_months(start_date, end_date)
        except ValueError as error:
            return ExperienceDuration(error=str(error))
        # Confidence documents date precision, not candidate quality. Year-only
        # dates are estimated and should be read as weaker duration evidence.
        start_is_precise = start_precision in {"day", "month"}
        end_is_precise = end_precision in {"day", "month", "present"}
        confidence = 0.95 if start_is_precise and end_is_precise else 0.60 if "year" in {start_precision, end_precision} else 0.75
        return ExperienceDuration(start_date=start_date.strftime("%Y-%m"), end_date=end_date.strftime("%Y-%m"), duration_months=duration, duration_years=round(duration / 12, 2), start_precision=start_precision, end_precision=end_precision, calculation_source="date_range", confidence=confidence, estimated="year" in {start_precision, end_precision})
    declared = parse_explicit_duration(declared_duration)
    if declared is not None:
        # Declared durations are accepted when dates cannot be parsed, but they
        # cannot participate in overlap removal because no period is known.
        return ExperienceDuration(duration_months=declared, duration_years=round(declared / 12, 2), calculation_source="explicit_duration", confidence=0.75)
    return ExperienceDuration(error="Impossible d'interpreter les dates ou la duree declaree.")


def enrich_experience_durations(experiences: list[Experience], today: date | None = None) -> list[Experience]:
    for experience in experiences:
        duration = calculate_experience_duration(experience.start_date, experience.end_date, experience.declared_duration, today=today)
        experience.duration = duration
        # duration_months duplicates duration.duration_months for legacy callers;
        # schema simplification can remove it once those callers use duration.
        experience.duration_months = duration.duration_months
    return experiences


def experience_to_period(experience: Experience) -> ExperiencePeriod | None:
    duration = experience.duration
    if not duration or not duration.start_date or not duration.end_date or duration.duration_months is None:
        return None
    return ExperiencePeriod(start_date=duration.start_date, end_date=duration.end_date, duration_months=duration.duration_months, confidence=duration.confidence)


# Role dans le projet:
# Ce fichier calcule les durees d'experience a partir de dates ou durees declarees. Le CVExtractor l'utilise avant le matching d'experience.
