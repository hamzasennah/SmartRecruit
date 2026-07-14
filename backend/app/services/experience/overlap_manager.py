from __future__ import annotations

from datetime import date

from app.services.normalization.date_normalizer import calculate_months


def parse_period_value(value: str) -> date:
    year, month = value.split("-", 1)
    return date(int(year), int(month), 1)


def merge_experience_periods(periods: list[tuple[date, date]]) -> list[tuple[date, date]]:
    if not periods:
        return []
    sorted_periods = sorted(periods, key=lambda period: period[0])
    merged = [sorted_periods[0]]
    for current_start, current_end in sorted_periods[1:]:
        previous_start, previous_end = merged[-1]
        if current_start <= previous_end:
            merged[-1] = (previous_start, max(previous_end, current_end))
        else:
            merged.append((current_start, current_end))
    return merged


def calculate_total_unique_months(periods: list[tuple[date, date]]) -> int:
    return sum(calculate_months(start, end) for start, end in merge_experience_periods(periods))

