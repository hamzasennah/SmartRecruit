from datetime import date

from app.services.experience.duration_calculator import calculate_experience_duration, parse_explicit_duration
from app.services.experience.overlap_manager import calculate_total_unique_months


def test_explicit_duration() -> None:
    assert parse_explicit_duration("2 ans et 6 mois") == 30


def test_date_range_duration() -> None:
    result = calculate_experience_duration("janvier 2021", "mars 2023")
    assert result.duration_months == 27
    assert result.confidence == 0.95


def test_french_abbreviated_month_range_duration() -> None:
    result = calculate_experience_duration("Mar 2022", "Juil 2022")
    assert result.duration_months == 5
    assert result.start_date == "2022-03"
    assert result.end_date == "2022-07"


def test_full_day_month_year_date_with_depuis_is_parsed() -> None:
    result = calculate_experience_duration("Depuis 22/04/2024", "Present", today=date(2025, 4, 1))
    assert result.duration_months == 13
    assert result.start_date == "2024-04"
    assert result.end_date == "2025-04"
    assert result.start_precision == "day"
    assert result.confidence == 0.95


def test_overlap_periods_not_counted_twice() -> None:
    periods = [(date(2021, 1, 1), date(2022, 12, 1)), (date(2022, 6, 1), date(2023, 12, 1))]
    assert calculate_total_unique_months(periods) == 36

# Role dans le projet:
# Ce fichier contient les tests unitaires pour experience. Il protege le comportement existant pendant les refactors sans appeler les services externes.
