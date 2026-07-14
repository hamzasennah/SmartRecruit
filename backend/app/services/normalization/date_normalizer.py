from __future__ import annotations

import re
import unicodedata
from datetime import date

MONTHS = {"janvier":1,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,"juillet":7,"aout":8,"septembre":9,"octobre":10,"novembre":11,"decembre":12,"january":1,"february":2,"march":3,"april":4,"may":5,"june":6,"july":7,"august":8,"september":9,"october":10,"november":11,"december":12,"jan":1,"fev":2,"feb":2,"mar":3,"avr":4,"apr":4,"jun":6,"jul":7,"aou":8,"aug":8,"sep":9,"sept":9,"oct":10,"nov":11,"dec":12}
PRESENT_WORDS = {"present","aujourdhui","actuellement","current","now","en cours"}


def parse_month_year(value: str | None, today: date | None = None) -> tuple[date | None, str]:
    if not value:
        return None, "unknown"
    today = today or date.today()
    normalized = _normalize_date_text(value).replace("'", "")
    if normalized in PRESENT_WORDS:
        return date(today.year, today.month, 1), "present"
    match = re.fullmatch(r"(0?[1-9]|1[0-2])[/.-](19\d{2}|20\d{2})", normalized)
    if match:
        return date(int(match.group(2)), int(match.group(1)), 1), "month"
    match = re.fullmatch(r"(19\d{2}|20\d{2})[/.-](0?[1-9]|1[0-2])", normalized)
    if match:
        return date(int(match.group(1)), int(match.group(2)), 1), "month"
    match = re.fullmatch(r"([a-z]+)\s+(19\d{2}|20\d{2})", normalized)
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


def _normalize_date_text(value: str) -> str:
    value = value.lower().strip()
    value = "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")
    value = re.sub(r"\s+", " ", value)
    return value.strip()
