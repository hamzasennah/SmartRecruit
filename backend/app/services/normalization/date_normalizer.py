from __future__ import annotations

import re
import unicodedata
from datetime import date

MONTHS = {
    "janvier": 1,
    "janv": 1,
    "january": 1,
    "jan": 1,
    "fevrier": 2,
    "fevr": 2,
    "fev": 2,
    "february": 2,
    "feb": 2,
    "mars": 3,
    "march": 3,
    "mar": 3,
    "avril": 4,
    "avr": 4,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "may": 5,
    "juin": 6,
    "june": 6,
    "jun": 6,
    "juillet": 7,
    "juil": 7,
    "juill": 7,
    "july": 7,
    "jul": 7,
    "aout": 8,
    "aou": 8,
    "august": 8,
    "aug": 8,
    "septembre": 9,
    "sept": 9,
    "september": 9,
    "sep": 9,
    "octobre": 10,
    "october": 10,
    "oct": 10,
    "novembre": 11,
    "november": 11,
    "nov": 11,
    "decembre": 12,
    "december": 12,
    "dec": 12,
}

PRESENT_WORDS = {
    "present",
    "aujourdhui",
    "a ce jour",
    "actuellement",
    "current",
    "currently",
    "now",
    "en cours",
    "ongoing",
    "to date",
    "jusqua present",
    "jusqu a present",
    "presentement",
}

DATE_PREFIX_PATTERN = r"^(?:depuis|since|from|a partir de|a compter de|du|de|le)\s+"
CURRENT_START_PATTERN = r"^(?:depuis|since|a partir de|a compter de)\b"


def parse_month_year(value: str | None, today: date | None = None) -> tuple[date | None, str]:
    if not value:
        return None, "unknown"
    today = today or date.today()
    normalized = normalize_date_text(value)
    if is_present_value(normalized):
        return date(today.year, today.month, 1), "present"

    normalized = re.sub(DATE_PREFIX_PATTERN, "", normalized).strip()
    if is_present_value(normalized):
        return date(today.year, today.month, 1), "present"

    match = re.fullmatch(r"(19\d{2}|20\d{2})[/.-](0?[1-9]|1[0-2])[/.-](0?[1-9]|[12]\d|3[01])", normalized)
    if match:
        parsed = _safe_day_month_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return (parsed, "day") if parsed else (None, "unknown")

    match = re.fullmatch(r"(0?[1-9]|[12]\d|3[01])[/.-](0?[1-9]|[12]\d|3[01])[/.-](19\d{2}|20\d{2})", normalized)
    if match:
        parsed = _parse_numeric_day_month(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return (parsed, "day") if parsed else (None, "unknown")

    match = re.fullmatch(r"(0?[1-9]|1[0-2])[/.-](19\d{2}|20\d{2})", normalized)
    if match:
        return date(int(match.group(2)), int(match.group(1)), 1), "month"

    match = re.fullmatch(r"(19\d{2}|20\d{2})[/.-](0?[1-9]|1[0-2])", normalized)
    if match:
        return date(int(match.group(1)), int(match.group(2)), 1), "month"

    match = re.fullmatch(r"(?:0?[1-9]|[12]\d|3[01])?\s*([a-z]+)\s+(19\d{2}|20\d{2})", normalized)
    if match and match.group(1) in MONTHS:
        return date(int(match.group(2)), MONTHS[match.group(1)], 1), "month"

    match = re.fullmatch(r"(19\d{2}|20\d{2})", normalized)
    if match:
        return date(int(match.group(1)), 7, 1), "year"

    return None, "unknown"


def calculate_months(start_date: date, end_date: date, inclusive: bool = True) -> int:
    if end_date < start_date:
        raise ValueError("La date de fin est anterieure a la date de debut.")
    months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month
    return months + 1 if inclusive else months


def has_current_start_marker(value: str | None) -> bool:
    return bool(value and re.search(CURRENT_START_PATTERN, normalize_date_text(value)))


def is_present_value(value: str | None) -> bool:
    return bool(value and normalize_date_text(value) in PRESENT_WORDS)


def normalize_date_text(value: str) -> str:
    value = value.lower().strip()
    value = "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")
    value = value.replace("'", "")
    value = re.sub(r"(?<=[a-z])\.", "", value)
    value = re.sub(r"[,;:]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _safe_day_month_date(year: int, month: int, day: int) -> date | None:
    try:
        date(year, month, day)
    except ValueError:
        return None
    return date(year, month, 1)


def _parse_numeric_day_month(first: int, second: int, year: int) -> date | None:
    if first > 12 and second <= 12:
        day, month = first, second
    elif second > 12 and first <= 12:
        month, day = first, second
    else:
        day, month = first, second
    return _safe_day_month_date(year, month, day)


def _normalize_date_text(value: str) -> str:
    return normalize_date_text(value)


# Role dans le projet:
# Ce fichier normalise dates et mois bilingues. Les calculs d'experience l'utilisent pour transformer du texte CV en periodes comparables.
